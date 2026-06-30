"""Finogrid Agent Ledger — core business logic.

Implements the full A2A micropay flow with:
- Agent registration + API key generation
- KYA (Know Your Agent) submission and polling
- Wallet creation (open/closed loop)
- Payment intent reservation
- 10-gate compliance micropay sequence
- Double-entry ledger entries
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from demo.finogrid.models import (
    Client, AgentAccount, AgentKYA, AgentWallet, AgentLedgerEntry,
    PaymentIntent, MicroTransaction, Batch, PayoutTask,
    KYAStatus, AgentStatus, LoopType, IntentStatus, MicroTxStatus,
    _new_uuid, _utcnow,
)


# ========== Agent Registration ==========

def _hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def _generate_api_key() -> str:
    return f"fig_agent_{secrets.token_hex(24)}"


async def create_agent(db: AsyncSession, name: str, owner_client_id: str, chain: str = "base") -> dict:
    """Register a new agent account. Returns agent data + one-time API key."""
    api_key = _generate_api_key()
    api_key_hash = _hash_api_key(api_key)

    agent = AgentAccount(
        id=_new_uuid(),
        name=name,
        owner_client_id=owner_client_id,
        api_key_hash=api_key_hash,
        chain=chain,
    )
    db.add(agent)
    await db.flush()

    # Create ledger entry for account creation
    entry = AgentLedgerEntry(
        id=_new_uuid(),
        agent_account_id=agent.id,
        entry_type="credit",
        amount_usdc=0.0,
        balance_after=0.0,
        reserved_balance_after=0.0,
        description=f"Agent account created: {name}",
    )
    db.add(entry)
    await db.commit()

    return {
        "agent_account_id": agent.id,
        "name": agent.name,
        "api_key": api_key,
        "kya_status": agent.kya_status,
    }


# ========== KYA ==========

async def submit_kya(db: AsyncSession, agent_id: str, agent_purpose: str,
                     declared_use_case: str, agent_owner_attestation: str,
                     validator_name: str = "internal") -> dict:
    """Submit KYA verification for an agent."""
    # Check agent exists
    agent = await db.get(AgentAccount, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    if agent.status != AgentStatus.ACTIVE.value:
        raise ValueError(f"Agent is {agent.status}")

    # Check if KYA already exists
    existing = await db.execute(
        select(AgentKYA).where(AgentKYA.agent_account_id == agent_id)
    )
    kya = existing.scalar_one_or_none()
    if kya and kya.status == KYAStatus.ENHANCED.value:
        raise ValueError("KYA already at enhanced level")

    validator_ref = f"kyv_{uuid.uuid4().hex[:12]}"

    if kya:
        # Update existing KYA
        kya.agent_purpose = agent_purpose
        kya.declared_use_case = declared_use_case
        kya.agent_owner_attestation = agent_owner_attestation
        kya.validator_name = validator_name
        kya.validator_ref = validator_ref
        kya.status = KYAStatus.PENDING.value
        kya.kya_level = KYAStatus.PENDING.value
        kya.submitted_at = _utcnow()
    else:
        kya = AgentKYA(
            id=_new_uuid(),
            agent_account_id=agent_id,
            agent_purpose=agent_purpose,
            declared_use_case=declared_use_case,
            agent_owner_attestation=agent_owner_attestation,
            validator_name=validator_name,
            validator_ref=validator_ref,
        )
        db.add(kya)

    # Update agent status
    agent.kya_status = KYAStatus.PENDING.value

    await db.commit()
    await db.refresh(kya)

    return {
        "agent_account_id": agent_id,
        "kya_status": kya.status,
        "kya_level": kya.kya_level,
        "validator_ref": kya.validator_ref,
    }


async def get_kya_status(db: AsyncSession, agent_id: str) -> dict:
    """Get KYA status. In demo mode, auto-approves basic KYA after submission."""
    agent = await db.get(AgentAccount, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    kya_result = await db.execute(
        select(AgentKYA).where(AgentKYA.agent_account_id == agent_id)
    )
    kya = kya_result.scalar_one_or_none()

    if not kya:
        return {
            "agent_account_id": agent_id,
            "kya_status": KYAStatus.UNVERIFIED.value,
            "kya_level": KYAStatus.UNVERIFIED.value,
            "validator_name": "none",
            "validated_at": None,
            "message": "No KYA submission found. Submit KYA first.",
        }

    # Demo: auto-approve pending KYA to 'basic' after 1 second of submission
    if kya.status == KYAStatus.PENDING.value:
        elapsed = (_utcnow() - kya.submitted_at).total_seconds() if kya.submitted_at else 999
        if elapsed > 0:  # Immediate approval in demo mode
            kya.status = KYAStatus.BASIC.value
            kya.kya_level = KYAStatus.BASIC.value
            kya.validated_at = _utcnow()
            agent.kya_status = KYAStatus.BASIC.value
            await db.commit()

    return {
        "agent_account_id": agent_id,
        "kya_status": kya.status,
        "kya_level": kya.kya_level,
        "validator_name": kya.validator_name,
        "validated_at": kya.validated_at,
        "message": f"KYA level: {kya.kya_level}",
    }


# ========== Top Up (Demo: manual balance credit) ==========

async def topup_agent(db: AsyncSession, agent_id: str, amount_usdc: float,
                      deposit_tx_hash: str = "") -> dict:
    """Add USDC to agent's prefund balance (simulates on-chain deposit detection)."""
    agent = await db.get(AgentAccount, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    agent.prefund_balance_usdc += amount_usdc

    # Ledger entry
    entry = AgentLedgerEntry(
        id=_new_uuid(),
        agent_account_id=agent_id,
        entry_type="credit",
        amount_usdc=amount_usdc,
        balance_after=agent.prefund_balance_usdc,
        reserved_balance_after=agent.reserved_balance_usdc,
        description=f"Top-up via {deposit_tx_hash or 'demo deposit'}",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(agent)

    return {
        "agent_account_id": agent_id,
        "amount_usdc": amount_usdc,
        "new_balance": agent.prefund_balance_usdc,
        "status": "credited",
    }


# ========== Wallet ==========

async def create_wallet(db: AsyncSession, agent_id: str, label: str,
                        wallet_address: str, loop_type: str,
                        max_per_tx_usdc: float = 0.10,
                        max_daily_usdc: float = 1.00,
                        allowed_counterparties: list = None,
                        expires_at: datetime = None,
                        max_uses: int = None) -> dict:
    """Create a sub-wallet for an agent."""
    agent = await db.get(AgentAccount, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")
    if agent.status != AgentStatus.ACTIVE.value:
        raise ValueError(f"Agent is {agent.status}")
    if agent.kya_status not in (KYAStatus.BASIC.value, KYAStatus.ENHANCED.value):
        raise ValueError(f"KYA required. Current: {agent.kya_status}")

    if loop_type not in (LoopType.OPEN.value, LoopType.CLOSED.value):
        raise ValueError(f"Invalid loop_type: {loop_type}. Use 'open' or 'closed'.")

    wallet = AgentWallet(
        id=_new_uuid(),
        agent_account_id=agent_id,
        label=label,
        wallet_address=wallet_address,
        loop_type=loop_type,
        max_per_tx_usdc=max_per_tx_usdc,
        max_daily_usdc=max_daily_usdc,
        allowed_counterparties=allowed_counterparties or [],
        expires_at=expires_at,
        max_uses=max_uses,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)

    return {
        "wallet_id": wallet.id,
        "agent_account_id": agent_id,
        "label": wallet.label,
        "wallet_address": wallet.wallet_address,
        "loop_type": wallet.loop_type,
        "status": wallet.status,
        "spending_rules": {
            "max_per_tx_usdc": wallet.max_per_tx_usdc,
            "max_daily_usdc": wallet.max_daily_usdc,
            "daily_spent_usdc": wallet.daily_spent_usdc,
            "allowed_counterparties": wallet.allowed_counterparties,
            "max_uses": wallet.max_uses,
            "use_count": wallet.use_count,
        },
        "created_at": wallet.created_at,
    }


async def list_wallets(db: AsyncSession, agent_id: str) -> list:
    """List all wallets for an agent."""
    result = await db.execute(
        select(AgentWallet).where(AgentWallet.agent_account_id == agent_id)
    )
    wallets = result.scalars().all()
    return [
        {
            "wallet_id": w.id,
            "agent_account_id": w.agent_account_id,
            "label": w.label,
            "wallet_address": w.wallet_address,
            "loop_type": w.loop_type,
            "status": w.status,
            "spending_rules": {
                "max_per_tx_usdc": w.max_per_tx_usdc,
                "max_daily_usdc": w.max_daily_usdc,
                "daily_spent_usdc": w.daily_spent_usdc,
                "allowed_counterparties": w.allowed_counterparties,
                "max_uses": w.max_uses,
                "use_count": w.use_count,
            },
            "created_at": w.created_at,
        }
        for w in wallets
    ]


# ========== Payment Intent ==========

async def create_payment_intent(db: AsyncSession, payer_wallet_id: str,
                                amount_usdc: float, intent_description: str,
                                intent_category: str, expires_at: datetime) -> dict:
    """Reserve funds with a payment intent (closed-loop wallets only)."""
    wallet = await db.get(AgentWallet, payer_wallet_id)
    if not wallet:
        raise ValueError(f"Wallet {payer_wallet_id} not found")
    if wallet.loop_type != LoopType.CLOSED.value:
        raise ValueError(f"Payment intents only apply to closed-loop wallets. This wallet is {wallet.loop_type}.")
    if wallet.status != "active":
        raise ValueError(f"Wallet is {wallet.status}")

    agent = await db.get(AgentAccount, wallet.agent_account_id)
    if not agent:
        raise ValueError("Agent not found")

    # Reserve funds from available balance
    available = agent.prefund_balance_usdc - agent.reserved_balance_usdc
    if amount_usdc > available:
        raise ValueError(
            f"Insufficient available balance. Need ${amount_usdc:.2f}, "
            f"have ${available:.2f} (${agent.reserved_balance_usdc:.2f} reserved)"
        )

    # Create intent
    intent = PaymentIntent(
        id=_new_uuid(),
        payer_wallet_id=payer_wallet_id,
        amount_usdc=amount_usdc,
        intent_description=intent_description,
        intent_category=intent_category,
        expires_at=expires_at,
    )
    db.add(intent)

    # Reserve balance
    agent.reserved_balance_usdc += amount_usdc

    # Ledger entry
    entry = AgentLedgerEntry(
        id=_new_uuid(),
        agent_account_id=agent.id,
        entry_type="intent_reserve",
        amount_usdc=amount_usdc,
        balance_after=agent.prefund_balance_usdc,
        reserved_balance_after=agent.reserved_balance_usdc,
        payment_intent_id=intent.id,
        description=f"Intent reserved: {intent_description}",
    )
    db.add(entry)

    await db.commit()
    await db.refresh(intent)

    return {
        "payment_intent_id": intent.id,
        "payer_wallet_id": payer_wallet_id,
        "amount_usdc": intent.amount_usdc,
        "intent_description": intent.intent_description,
        "intent_category": intent.intent_category,
        "status": intent.status,
        "expires_at": intent.expires_at,
    }


# ========== Micropay (10-Gate Compliance Sequence) ==========

async def execute_micropay(db: AsyncSession, idempotency_key: str,
                           payer_wallet_id: str, payee_address: str,
                           amount_usdc: float, payment_intent_id: str = None,
                           x402_resource_url: str = None) -> dict:
    """Execute an agent micropayment with full 10-gate compliance check."""

    gates_passed = []

    # ---- Gate 1: Idempotency check ----
    existing = await db.execute(
        select(MicroTransaction).where(
            MicroTransaction.idempotency_key == idempotency_key
        )
    )
    cached = existing.scalar_one_or_none()
    if cached:
        gates_passed.append("1. idempotency: cached")
        agent = await db.get(AgentAccount, (await db.get(AgentWallet, cached.payer_wallet_id)).agent_account_id)
        return {
            "transaction_id": cached.id,
            "idempotency_key": cached.idempotency_key,
            "payer_wallet_id": cached.payer_wallet_id,
            "payee_address": cached.payee_address,
            "amount_usdc": cached.amount_usdc,
            "status": cached.status,
            "payer_available_balance_after": agent.prefund_balance_usdc - agent.reserved_balance_usdc if agent else 0,
            "settled_at": cached.settled_at or _utcnow(),
            "gates_passed": gates_passed + ["(replayed from cache)"],
        }
    gates_passed.append("1. idempotency: new")

    # ---- Gate 2: Wallet ownership + KYA ----
    wallet = await db.get(AgentWallet, payer_wallet_id)
    if not wallet:
        raise ValueError("Gate 2 FAILED: Wallet not found")
    if wallet.status != "active":
        raise ValueError(f"Gate 2 FAILED: Wallet is {wallet.status}")

    agent = await db.get(AgentAccount, wallet.agent_account_id)
    if not agent:
        raise ValueError("Gate 2 FAILED: Agent not found")
    if agent.status != AgentStatus.ACTIVE.value:
        raise ValueError(f"Gate 2 FAILED: Agent is {agent.status}")
    if agent.kya_status not in (KYAStatus.BASIC.value, KYAStatus.ENHANCED.value):
        raise ValueError(f"Gate 2 FAILED: KYA required. Current: {agent.kya_status}")
    gates_passed.append("2. KYA + wallet ownership: OK")

    # ---- Gate 3: Loop type / Intent validation ----
    if wallet.loop_type == LoopType.CLOSED.value:
        if not payment_intent_id:
            raise ValueError("Gate 3 FAILED: Closed-loop wallet requires payment_intent_id")
        intent = await db.get(PaymentIntent, payment_intent_id)
        if not intent:
            raise ValueError("Gate 3 FAILED: Payment intent not found")
        if intent.payer_wallet_id != payer_wallet_id:
            raise ValueError("Gate 3 FAILED: Intent does not belong to this wallet")
        if intent.status != IntentStatus.RESERVED.value:
            raise ValueError(f"Gate 3 FAILED: Intent status is {intent.status}")
        if abs(intent.amount_usdc - amount_usdc) > 0.001:
            raise ValueError(f"Gate 3 FAILED: Amount mismatch. Intent: ${intent.amount_usdc:.2f}, Request: ${amount_usdc:.2f}")
        if intent.expires_at < _utcnow():
            raise ValueError("Gate 3 FAILED: Payment intent expired")
        gates_passed.append("3. intent validation: OK (closed-loop)")
    else:
        gates_passed.append("3. loop type: open-loop (no intent needed)")

    # ---- Gate 4: Counterparty allowlist ----
    if wallet.allowed_counterparties and len(wallet.allowed_counterparties) > 0:
        if payee_address not in wallet.allowed_counterparties:
            raise ValueError(f"Gate 4 FAILED: Payee {payee_address[:10]}... not in allowlist")
    gates_passed.append("4. counterparty allowlist: OK")

    # ---- Gate 5: Per-transaction cap ----
    if amount_usdc > wallet.max_per_tx_usdc:
        raise ValueError(f"Gate 5 FAILED: Exceeds per-tx cap ${wallet.max_per_tx_usdc:.2f}")
    gates_passed.append("5. per-tx cap: OK")

    # ---- Gate 6: Daily velocity (wallet-level) ----
    # Reset daily counter if day changed
    now = _utcnow()
    if wallet.daily_reset_at and wallet.daily_reset_at.date() < now.date():
        wallet.daily_spent_usdc = 0.0
        wallet.daily_reset_at = now

    if wallet.daily_spent_usdc + amount_usdc > wallet.max_daily_usdc:
        raise ValueError(
            f"Gate 6 FAILED: Would exceed daily cap. "
            f"Spent: ${wallet.daily_spent_usdc:.2f}, Cap: ${wallet.max_daily_usdc:.2f}"
        )
    gates_passed.append("6. wallet daily velocity: OK")

    # ---- Gate 7: KYA-level daily aggregate ----
    kya_daily_limit = 100.0 if agent.kya_status == KYAStatus.ENHANCED.value else 1.0
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_total_result = await db.execute(
        select(func.coalesce(func.sum(MicroTransaction.amount_usdc), 0.0)).where(
            and_(
                MicroTransaction.payer_wallet_id.in_(
                    select(AgentWallet.id).where(AgentWallet.agent_account_id == agent.id)
                ),
                MicroTransaction.status.in_([MicroTxStatus.SETTLED_OFFCHAIN.value,
                                              MicroTxStatus.SETTLED_ONCHAIN.value]),
                MicroTransaction.created_at >= today_start,
            )
        )
    )
    daily_total = daily_total_result.scalar()
    if daily_total + amount_usdc > kya_daily_limit:
        raise ValueError(
            f"Gate 7 FAILED: KYA daily limit exceeded. "
            f"Spent today: ${daily_total:.2f}, Limit: ${kya_daily_limit:.2f} (level: {agent.kya_status})"
        )
    gates_passed.append("7. KYA daily aggregate: OK")

    # ---- Gate 8: Wallet expiry + max uses ----
    if wallet.expires_at and wallet.expires_at < now:
        raise ValueError("Gate 8 FAILED: Wallet expired")
    if wallet.max_uses is not None and wallet.use_count >= wallet.max_uses:
        raise ValueError(f"Gate 8 FAILED: Max uses ({wallet.max_uses}) reached")
    gates_passed.append("8. wallet expiry/uses: OK")

    # ---- Gate 9: Balance sufficiency ----
    if wallet.loop_type == LoopType.CLOSED.value:
        # Closed-loop: balance was already reserved via intent
        available_for_tx = amount_usdc  # already reserved
    else:
        available = agent.prefund_balance_usdc - agent.reserved_balance_usdc
        if amount_usdc > available:
            raise ValueError(
                f"Gate 9 FAILED: Insufficient funds. "
                f"Need: ${amount_usdc:.2f}, Available: ${available:.2f}"
            )
    gates_passed.append("9. balance sufficiency: OK")

    # ---- Gate 10: Execute (off-chain settlement) ----
    tx = MicroTransaction(
        id=_new_uuid(),
        idempotency_key=idempotency_key,
        payer_wallet_id=payer_wallet_id,
        payee_address=payee_address,
        amount_usdc=amount_usdc,
        chain=wallet.chain,
        loop_type=wallet.loop_type,
        payment_intent_id=payment_intent_id,
        x402_resource_url=x402_resource_url,
        status=MicroTxStatus.SETTLED_OFFCHAIN.value,
        settled_at=now,
    )
    db.add(tx)

    # Update balances
    agent.prefund_balance_usdc -= amount_usdc
    if payment_intent_id:
        agent.reserved_balance_usdc -= amount_usdc
        # Mark intent as consumed
        intent = await db.get(PaymentIntent, payment_intent_id)
        intent.status = IntentStatus.CONSUMED.value
        intent.consumed_micro_tx_id = tx.id

    # Update wallet counters
    wallet.daily_spent_usdc += amount_usdc
    wallet.use_count += 1

    # Ledger entry
    entry = AgentLedgerEntry(
        id=_new_uuid(),
        agent_account_id=agent.id,
        entry_type="debit",
        amount_usdc=amount_usdc,
        balance_after=agent.prefund_balance_usdc,
        reserved_balance_after=agent.reserved_balance_usdc,
        micro_tx_id=tx.id,
        payment_intent_id=payment_intent_id,
        description=f"Micropay to {payee_address[:10]}... — {wallet.label}",
    )
    db.add(entry)
    gates_passed.append("10. off-chain settlement: OK")

    await db.commit()
    await db.refresh(tx)

    return {
        "transaction_id": tx.id,
        "idempotency_key": tx.idempotency_key,
        "payer_wallet_id": tx.payer_wallet_id,
        "payee_address": tx.payee_address,
        "amount_usdc": tx.amount_usdc,
        "status": tx.status,
        "payer_available_balance_after": agent.prefund_balance_usdc - agent.reserved_balance_usdc,
        "settled_at": tx.settled_at,
        "gates_passed": gates_passed,
    }


# ========== Balance ==========

async def get_balance(db: AsyncSession, agent_id: str) -> dict:
    """Get agent balance and recent ledger entries."""
    agent = await db.get(AgentAccount, agent_id)
    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    entries_result = await db.execute(
        select(AgentLedgerEntry)
        .where(AgentLedgerEntry.agent_account_id == agent_id)
        .order_by(AgentLedgerEntry.created_at.desc())
        .limit(20)
    )
    entries = entries_result.scalars().all()

    return {
        "agent_account_id": agent.id,
        "prefund_balance_usdc": agent.prefund_balance_usdc,
        "reserved_balance_usdc": agent.reserved_balance_usdc,
        "available_balance_usdc": agent.prefund_balance_usdc - agent.reserved_balance_usdc,
        "kya_status": agent.kya_status,
        "recent_entries": [
            {
                "entry_type": e.entry_type,
                "amount_usdc": e.amount_usdc,
                "balance_after": e.balance_after,
                "reserved_balance_after": e.reserved_balance_after,
                "description": e.description,
                "created_at": e.created_at,
            }
            for e in entries
        ],
    }


# ========== Client Management (for demo) ==========

async def create_client(db: AsyncSession, name: str, email: str) -> dict:
    """Create a B2B client (needed as owner for agents)."""
    client = Client(
        id=_new_uuid(),
        name=name,
        email=email,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return {"client_id": client.id, "name": client.name, "email": client.email}

"""Finogrid API routes — Agent Ledger + B2B Payout endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from demo.finogrid.database import get_session
from demo.finogrid.schemas import (
    CreateAgentRequest, CreateAgentResponse,
    SubmitKYARequest, SubmitKYAResponse, KYAStatusResponse,
    CreateWalletRequest, WalletResponse, WalletListResponse,
    CreatePaymentIntentRequest, PaymentIntentResponse,
    MicropayRequest, MicropayResponse,
    TopupRequest, TopupResponse,
    BalanceResponse,
    CreateBatchRequest, BatchResponse,
)
from demo.finogrid.agent_ledger import (
    create_agent, submit_kya, get_kya_status, topup_agent,
    create_wallet, list_wallets,
    create_payment_intent, execute_micropay, get_balance,
    create_client,
)
from demo.finogrid.payout import create_batch
from demo.finogrid.corridors import list_corridors, get_corridor, validate_beneficiary


router = APIRouter(prefix="/api/finogrid", tags=["Finogrid"])


# ========== Health ==========

@router.get("/health")
async def health():
    return {"status": "ok", "module": "Finogrid", "mode": "demo"}


# ========== Client Management (for demo setup) ==========

@router.post("/clients")
async def register_client(name: str, email: str, db: AsyncSession = Depends(get_session)):
    """Create a B2B client. Required before registering agents."""
    try:
        result = await create_client(db, name, email)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Agents ==========

@router.post("/agents", response_model=CreateAgentResponse)
async def register_agent(req: CreateAgentRequest, db: AsyncSession = Depends(get_session)):
    """Register a new AI agent account. Returns the API key ONCE."""
    try:
        result = await create_agent(db, req.name, req.owner_client_id, req.chain)
        return CreateAgentResponse(
            agent_account_id=result["agent_account_id"],
            name=result["name"],
            api_key=result["api_key"],
            kya_status=result["kya_status"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== KYA ==========

@router.post("/agents/{agent_id}/kya", response_model=SubmitKYAResponse)
async def agent_submit_kya(agent_id: str, req: SubmitKYARequest,
                           db: AsyncSession = Depends(get_session)):
    """Submit KYA (Know Your Agent) verification."""
    try:
        result = await submit_kya(
            db, agent_id, req.agent_purpose, req.declared_use_case,
            req.agent_owner_attestation, req.validator_name,
        )
        return SubmitKYAResponse(
            agent_account_id=result["agent_account_id"],
            kya_status=result["kya_status"],
            kya_level=result["kya_level"],
            validator_ref=result["validator_ref"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/agents/{agent_id}/kya", response_model=KYAStatusResponse)
async def agent_get_kya(agent_id: str, db: AsyncSession = Depends(get_session)):
    """Get KYA status. In demo mode, auto-approves pending submissions."""
    try:
        result = await get_kya_status(db, agent_id)
        return KYAStatusResponse(
            agent_account_id=result["agent_account_id"],
            kya_status=result["kya_status"],
            kya_level=result["kya_level"],
            validator_name=result["validator_name"],
            validated_at=result.get("validated_at"),
            message=result.get("message", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== Balance & Top-up ==========

@router.post("/agents/{agent_id}/topup", response_model=TopupResponse)
async def agent_topup(agent_id: str, req: TopupRequest,
                      db: AsyncSession = Depends(get_session)):
    """Top up agent balance (simulates on-chain deposit detection)."""
    try:
        result = await topup_agent(db, agent_id, req.amount_usdc, req.deposit_tx_hash)
        return TopupResponse(
            agent_account_id=result["agent_account_id"],
            amount_usdc=result["amount_usdc"],
            new_balance=result["new_balance"],
            status=result["status"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/agents/{agent_id}/balance", response_model=BalanceResponse)
async def agent_balance(agent_id: str, db: AsyncSession = Depends(get_session)):
    """Get agent balance, reserved amount, and recent ledger entries."""
    try:
        result = await get_balance(db, agent_id)
        return BalanceResponse(
            agent_account_id=result["agent_account_id"],
            prefund_balance_usdc=result["prefund_balance_usdc"],
            reserved_balance_usdc=result["reserved_balance_usdc"],
            available_balance_usdc=result["available_balance_usdc"],
            kya_status=result["kya_status"],
            recent_entries=result["recent_entries"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========== Wallets ==========

@router.post("/agents/{agent_id}/wallets", response_model=WalletResponse)
async def agent_create_wallet(agent_id: str, req: CreateWalletRequest,
                               db: AsyncSession = Depends(get_session)):
    """Create a sub-wallet (open-loop or closed-loop)."""
    try:
        result = await create_wallet(
            db, agent_id, req.label, req.wallet_address, req.loop_type,
            req.max_per_tx_usdc, req.max_daily_usdc,
            req.allowed_counterparties, req.expires_at, req.max_uses,
        )
        return WalletResponse(
            wallet_id=result["wallet_id"],
            agent_account_id=result["agent_account_id"],
            label=result["label"],
            wallet_address=result["wallet_address"],
            loop_type=result["loop_type"],
            status=result["status"],
            spending_rules=result["spending_rules"],
            created_at=result["created_at"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/agents/{agent_id}/wallets", response_model=WalletListResponse)
async def agent_list_wallets(agent_id: str, db: AsyncSession = Depends(get_session)):
    """List all wallets for an agent."""
    try:
        wallets = await list_wallets(db, agent_id)
        return WalletListResponse(agent_account_id=agent_id, wallets=wallets)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Payment Intents ==========

@router.post("/payment-intents", response_model=PaymentIntentResponse)
async def create_intent(req: CreatePaymentIntentRequest,
                        db: AsyncSession = Depends(get_session)):
    """Create a payment intent to reserve funds (closed-loop wallets only)."""
    try:
        result = await create_payment_intent(
            db, req.payer_wallet_id, req.amount_usdc,
            req.intent_description, req.intent_category, req.expires_at,
        )
        return PaymentIntentResponse(
            payment_intent_id=result["payment_intent_id"],
            payer_wallet_id=result["payer_wallet_id"],
            amount_usdc=result["amount_usdc"],
            intent_description=result["intent_description"],
            intent_category=result["intent_category"],
            status=result["status"],
            expires_at=result["expires_at"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Micropay ==========

@router.post("/micropay", response_model=MicropayResponse)
async def micropay(req: MicropayRequest, db: AsyncSession = Depends(get_session)):
    """Execute an agent-to-agent micropayment.

    Passes through the 10-gate compliance sequence:
    1. Idempotency check
    2. KYA + wallet ownership
    3. Loop type / PaymentIntent validation
    4. Counterparty allowlist
    5. Per-transaction cap
    6. Wallet daily velocity
    7. KYA-level daily aggregate
    8. Wallet expiry / max uses
    9. Balance sufficiency
    10. Off-chain settlement
    """
    try:
        result = await execute_micropay(
            db, req.idempotency_key, req.payer_wallet_id,
            req.payee_address, req.amount_usdc,
            req.payment_intent_id, req.x402_resource_url,
        )
        return MicropayResponse(
            transaction_id=result["transaction_id"],
            idempotency_key=result["idempotency_key"],
            payer_wallet_id=result["payer_wallet_id"],
            payee_address=result["payee_address"],
            amount_usdc=result["amount_usdc"],
            status=result["status"],
            payer_available_balance_after=result["payer_available_balance_after"],
            settled_at=result["settled_at"],
            gates_passed=result["gates_passed"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== B2B Payout ==========

@router.post("/batches", response_model=BatchResponse)
async def create_payout_batch(req: CreateBatchRequest,
                               db: AsyncSession = Depends(get_session)):
    """Create and process a B2B payout batch across international corridors."""
    try:
        result = await create_batch(db, req.client_id, req.reference, req.tasks)
        return BatchResponse(
            batch_id=result["batch_id"],
            client_id=result["client_id"],
            reference=result["reference"],
            status=result["status"],
            total_amount_usd=result["total_amount_usd"],
            task_count=result["task_count"],
            completed_count=result.get("completed_count", 0),
            failed_count=result.get("failed_count", 0),
            created_at=result["created_at"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== Corridors ==========

@router.get("/corridors")
async def corridors_list():
    """List all 8 supported payment corridors with their configurations."""
    return {
        "corridors": list_corridors(),
        "count": 8,
        "note": "Simplified for demo. Production uses full corridor adapters with live partner APIs.",
    }


@router.get("/corridors/{corridor_code}")
async def corridor_detail(corridor_code: str):
    """Get details for a specific corridor."""
    corridor = get_corridor(corridor_code.upper())
    if not corridor:
        raise HTTPException(status_code=404, detail=f"Unknown corridor: {corridor_code}")
    return corridor.to_dict()


@router.post("/corridors/{corridor_code}/validate")
async def corridor_validate_beneficiary(corridor_code: str, beneficiary_data: dict):
    """Validate beneficiary data against corridor requirements."""
    result = validate_beneficiary(corridor_code, beneficiary_data)
    if not result["valid"]:
        raise HTTPException(status_code=400, detail=result)
    return {"valid": True, "corridor_code": corridor_code.upper()}


# ========== x402 Protected Demo ==========

@router.get("/protected/premium-report")
async def premium_report():
    """x402-protected endpoint. Returns 402 unless request includes PAYMENT-SIGNATURE header."""
    return {
        "report": "Q4 2025 Institutional Crypto Flow Report",
        "insights": [
            "BTC ETF net inflows: $5.2B in Q4 (+240% QoQ)",
            "ETH staking yield compression to 3.2% as validator queue grows",
            "Stablecoin market cap hit $200B — USDC at $56B, USDT at $110B",
            "DeFi TVL crossed $120B, highest since 2022",
        ],
        "access_granted_via": "x402 micropayment (0.05 USDC on Base L2)",
        "note": "In production, this report costs 0.05 USDC via x402 protocol.",
    }

"""Finogrid data models — simplified for SQLite demo.

Mirrors the production schema from finogrid/database/models/ but uses SQLite
with UUID-as-text and simplified relationships for zero-config local execution.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, ForeignKey, Text, Enum, Boolean, JSON,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


# ========== Enums ==========

class KYAStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    BASIC = "basic"
    ENHANCED = "enhanced"


class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class LoopType(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class IntentStatus(str, enum.Enum):
    RESERVED = "reserved"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    SUPERSEDED = "superseded"


class IntentCategory(str, enum.Enum):
    COMPUTE = "compute"
    DATA = "data"
    AGENT_SERVICE = "agent_service"
    CONTENT = "content"
    OFFRAMP = "offramp"
    OTHER = "other"


class MicroTxStatus(str, enum.Enum):
    PENDING = "pending"
    SETTLED_OFFCHAIN = "settled_offchain"
    SETTLED_ONCHAIN = "settled_onchain"
    FAILED = "failed"
    REFUNDED = "refunded"


# ========== V1: B2B Payout Models ==========

class Client(Base):
    __tablename__ = "clients"

    id = Column(String, primary_key=True, default=_new_uuid)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    status = Column(String, default="active")  # active, suspended
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    batches = relationship("Batch", back_populates="client")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String, primary_key=True, default=_new_uuid)
    client_id = Column(String, ForeignKey("clients.id"), nullable=False)
    reference = Column(String, nullable=False)
    status = Column(String, default="draft")  # draft, pending, processing, completed, failed
    total_amount_usd = Column(Float, default=0.0)
    task_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    client = relationship("Client", back_populates="batches")
    tasks = relationship("PayoutTask", back_populates="batch")


class PayoutTask(Base):
    __tablename__ = "payout_tasks"

    id = Column(String, primary_key=True, default=_new_uuid)
    batch_id = Column(String, ForeignKey("batches.id"), nullable=False)
    corridor_code = Column(String(2), nullable=False)
    recipient_name = Column(String, nullable=False)
    amount_usd = Column(Float, nullable=False)
    preferred_asset = Column(String, default="USDC")
    preferred_mode = Column(String, default="wallet")  # wallet or fiat
    status = Column(String, default="pending")
    partner_tx_id = Column(String, nullable=True)
    failure_reason = Column(String, nullable=True)
    beneficiary_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    batch = relationship("Batch", back_populates="tasks")


# ========== V2: Agent Ledger Models ==========

class AgentAccount(Base):
    __tablename__ = "agent_accounts"

    id = Column(String, primary_key=True, default=_new_uuid)
    name = Column(String, nullable=False)
    owner_client_id = Column(String, ForeignKey("clients.id"), nullable=False)
    api_key_hash = Column(String, nullable=False, comment="SHA-256 hash of API key")
    status = Column(String, default=AgentStatus.ACTIVE.value)
    kya_status = Column(String, default=KYAStatus.UNVERIFIED.value)
    chain = Column(String, default="base")
    prefund_balance_usdc = Column(Float, default=0.0)
    reserved_balance_usdc = Column(Float, default=0.0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    kya = relationship("AgentKYA", back_populates="agent", uselist=False)
    wallets = relationship("AgentWallet", back_populates="agent")
    ledger_entries = relationship("AgentLedgerEntry", back_populates="agent")


class AgentKYA(Base):
    __tablename__ = "agent_kya"

    id = Column(String, primary_key=True, default=_new_uuid)
    agent_account_id = Column(String, ForeignKey("agent_accounts.id"), unique=True, nullable=False)
    status = Column(String, default=KYAStatus.PENDING.value)
    kya_level = Column(String, default=KYAStatus.PENDING.value)
    validator_name = Column(String, default="internal")
    validator_ref = Column(String, nullable=True)
    agent_purpose = Column(Text, nullable=True)
    declared_use_case = Column(String, nullable=True)  # trading_support, content_generation, etc.
    agent_owner_attestation = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=_utcnow)
    validated_at = Column(DateTime, nullable=True)

    agent = relationship("AgentAccount", back_populates="kya")


class AgentWallet(Base):
    __tablename__ = "agent_wallets"

    id = Column(String, primary_key=True, default=_new_uuid)
    agent_account_id = Column(String, ForeignKey("agent_accounts.id"), nullable=False)
    label = Column(String, nullable=False)
    wallet_address = Column(String, nullable=False)  # EVM address
    chain = Column(String, default="base")
    status = Column(String, default="active")
    loop_type = Column(String, nullable=False)  # open or closed
    max_per_tx_usdc = Column(Float, default=0.10)
    max_daily_usdc = Column(Float, default=1.00)
    daily_spent_usdc = Column(Float, default=0.0)
    daily_reset_at = Column(DateTime, default=_utcnow)
    allowed_counterparties = Column(JSON, nullable=True)  # list of addresses
    expires_at = Column(DateTime, nullable=True)
    max_uses = Column(Integer, nullable=True)
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    agent = relationship("AgentAccount", back_populates="wallets")
    payment_intents = relationship("PaymentIntent", back_populates="wallet")


class PaymentIntent(Base):
    __tablename__ = "payment_intents"

    id = Column(String, primary_key=True, default=_new_uuid)
    payer_wallet_id = Column(String, ForeignKey("agent_wallets.id"), nullable=False)
    amount_usdc = Column(Float, nullable=False)
    asset = Column(String, default="USDC")
    intent_description = Column(Text, nullable=False)
    intent_category = Column(String, default=IntentCategory.OTHER.value)
    status = Column(String, default=IntentStatus.RESERVED.value)
    expires_at = Column(DateTime, nullable=False)
    consumed_micro_tx_id = Column(String, nullable=True)
    superseded_by_intent_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    wallet = relationship("AgentWallet", back_populates="payment_intents")


class MicroTransaction(Base):
    __tablename__ = "micro_transactions"

    id = Column(String, primary_key=True, default=_new_uuid)
    idempotency_key = Column(String, unique=True, nullable=False, index=True)
    payer_wallet_id = Column(String, ForeignKey("agent_wallets.id"), nullable=False)
    payee_address = Column(String, nullable=False)
    payee_wallet_id = Column(String, nullable=True)
    amount_usdc = Column(Float, nullable=False)
    chain = Column(String, default="base")
    loop_type = Column(String, nullable=False)
    payment_intent_id = Column(String, nullable=True)
    x402_payment_header = Column(Text, nullable=True)
    x402_resource_url = Column(String, nullable=True)
    status = Column(String, default=MicroTxStatus.PENDING.value)
    on_chain_tx_hash = Column(String, nullable=True)
    failure_reason = Column(String, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("idx_microtx_idempotency", "idempotency_key"),
    )


class AgentLedgerEntry(Base):
    __tablename__ = "agent_ledger_entries"

    id = Column(String, primary_key=True, default=_new_uuid)
    agent_account_id = Column(String, ForeignKey("agent_accounts.id"), nullable=False)
    entry_type = Column(String, nullable=False)  # credit, debit, refund, fee, intent_reserve, intent_release
    amount_usdc = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)
    reserved_balance_after = Column(Float, nullable=False)
    micro_tx_id = Column(String, nullable=True)
    payment_intent_id = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    agent = relationship("AgentAccount", back_populates="ledger_entries")

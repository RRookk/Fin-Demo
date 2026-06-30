"""Finogrid API schemas — request/response Pydantic models."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# --- Agent Registration ---

class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["my-trading-agent"])
    owner_client_id: str = Field(..., description="Client ID that owns this agent")
    chain: str = Field(default="base", description="Blockchain for settlements")

class CreateAgentResponse(BaseModel):
    agent_account_id: str
    name: str
    api_key: str = Field(..., description="API key — returned ONCE, store securely")
    kya_status: str = "unverified"
    message: str = "Agent registered. Submit KYA to start transacting."


# --- KYA ---

class SubmitKYARequest(BaseModel):
    agent_purpose: str = Field(..., min_length=1, max_length=500,
        examples=["This agent retrieves financial data and generates analysis reports."])
    declared_use_case: str = Field(...,
        description="data_retrieval, content_generation, trading_support, or general",
        examples=["content_generation"])
    agent_owner_attestation: str = Field(..., min_length=1, max_length=500,
        examples=["I confirm I own and control this agent."])
    validator_name: str = Field(default="internal")

class SubmitKYAResponse(BaseModel):
    agent_account_id: str
    kya_status: str
    kya_level: str
    validator_ref: str
    message: str = "KYA submitted. Poll status to track verification."

class KYAStatusResponse(BaseModel):
    agent_account_id: str
    kya_status: str
    kya_level: str
    validator_name: str
    validated_at: Optional[datetime] = None
    message: str


# --- Wallet ---

class CreateWalletRequest(BaseModel):
    label: str = Field(..., examples=["inference-payments"])
    wallet_address: str = Field(..., min_length=42, max_length=42,
        description="EVM wallet address (0x...)",
        examples=["0x742d35Cc6634C0532925a3b844Bc9e7595f7bD18"])
    loop_type: str = Field(..., description="open (no intent needed) or closed (intent required)",
        examples=["closed"])
    max_per_tx_usdc: float = Field(default=0.10, description="Per-transaction cap in USDC")
    max_daily_usdc: float = Field(default=1.00, description="Daily spend cap in USDC")
    allowed_counterparties: Optional[List[str]] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None

class WalletResponse(BaseModel):
    wallet_id: str
    agent_account_id: str
    label: str
    wallet_address: str
    loop_type: str
    status: str
    spending_rules: dict
    created_at: datetime

class WalletListResponse(BaseModel):
    agent_account_id: str
    wallets: List[WalletResponse]


# --- Payment Intent ---

class CreatePaymentIntentRequest(BaseModel):
    payer_wallet_id: str
    amount_usdc: float = Field(..., gt=0, description="Amount to reserve in USDC")
    intent_description: str = Field(..., description="Purpose of the payment",
        examples=["Pay for GPT-4 inference — 50K tokens"])
    intent_category: str = Field(default="compute",
        description="compute, data, agent_service, content, offramp, other")
    expires_at: datetime = Field(..., description="Intent expiration time (UTC)")

class PaymentIntentResponse(BaseModel):
    payment_intent_id: str
    payer_wallet_id: str
    amount_usdc: float
    intent_description: str
    intent_category: str
    status: str
    expires_at: datetime
    message: str = "Payment intent created. Use intent_id in micropay request."


# --- Micropay ---

class MicropayRequest(BaseModel):
    idempotency_key: str = Field(...,
        description="Unique key to prevent double-spend (use UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"])
    payer_wallet_id: str
    payee_address: str = Field(..., min_length=42, max_length=42)
    amount_usdc: float = Field(..., gt=0)
    payment_intent_id: Optional[str] = Field(None,
        description="Required for closed-loop wallets")
    x402_resource_url: Optional[str] = None

class MicropayResponse(BaseModel):
    transaction_id: str
    idempotency_key: str
    payer_wallet_id: str
    payee_address: str
    amount_usdc: float
    status: str
    payer_available_balance_after: float
    settled_at: datetime
    gates_passed: List[str] = Field(default_factory=list,
        description="Compliance gates checked (10-gate sequence)")


# --- Top Up ---

class TopupRequest(BaseModel):
    deposit_tx_hash: str = Field(...,
        examples=["0xabc123..."])
    amount_usdc: float = Field(..., gt=0,
        description="Amount deposited in USDC")

class TopupResponse(BaseModel):
    agent_account_id: str
    amount_usdc: float
    new_balance: float
    status: str


# --- Balance ---

class LedgerEntryResponse(BaseModel):
    entry_type: str
    amount_usdc: float
    balance_after: float
    reserved_balance_after: float
    description: Optional[str]
    created_at: datetime

class BalanceResponse(BaseModel):
    agent_account_id: str
    prefund_balance_usdc: float
    reserved_balance_usdc: float
    available_balance_usdc: float
    kya_status: str
    recent_entries: List[LedgerEntryResponse]


# --- B2B Payout ---

class CreateBatchRequest(BaseModel):
    client_id: str
    reference: str
    tasks: List[dict] = Field(..., description="List of payout tasks [{corridor_code, recipient_name, amount_usd, preferred_asset, preferred_mode}]")

class BatchResponse(BaseModel):
    batch_id: str
    client_id: str
    reference: str
    status: str
    total_amount_usd: float
    task_count: int
    completed_count: int
    failed_count: int
    created_at: datetime

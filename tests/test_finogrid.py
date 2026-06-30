"""Tests for Finogrid API — full agent lifecycle flow."""

import pytest_asyncio
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import ASGITransport, AsyncClient
from demo.main import create_finogrid_app


@pytest_asyncio.fixture
async def client():
    from demo.finogrid.database import init_db
    await init_db()
    app = create_finogrid_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/finogrid/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_list_corridors(client):
    resp = await client.get("/api/finogrid/corridors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 8
    assert "BR" in [c["corridor_code"] for c in data["corridors"]]


@pytest.mark.asyncio
async def test_corridor_detail(client):
    resp = await client.get("/api/finogrid/corridors/BR")
    assert resp.status_code == 200
    assert resp.json()["country"] == "Brazil"


@pytest.mark.asyncio
async def test_corridor_not_found(client):
    resp = await client.get("/api/finogrid/corridors/XX")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_agent_lifecycle(client):
    """End-to-end: Client -> Agent -> KYA -> Topup -> Wallet -> Intent -> Micropay -> Balance"""
    uid = uuid.uuid4().hex[:8]

    # 1. Create client
    resp = await client.post(f"/api/finogrid/clients?name=TC_{uid}&email=t_{uid}@test.com")
    assert resp.status_code == 200
    client_id = resp.json()["client_id"]

    # 2. Create agent
    resp = await client.post("/api/finogrid/agents", json={
        "name": f"test-agent-{uid}",
        "owner_client_id": client_id,
        "chain": "base",
    })
    assert resp.status_code == 200
    agent = resp.json()
    agent_id = agent["agent_account_id"]
    api_key = agent["api_key"]
    assert api_key.startswith("fig_agent_")
    assert agent["kya_status"] == "unverified"

    # 3. Submit KYA
    resp = await client.post(f"/api/finogrid/agents/{agent_id}/kya", json={
        "agent_purpose": "Testing payment flow",
        "declared_use_case": "content_generation",
        "agent_owner_attestation": "I own this test agent",
        "validator_name": "internal",
    })
    assert resp.status_code == 200
    assert resp.json()["kya_status"] == "pending"

    # 4. Poll KYA (auto-approves in demo)
    resp = await client.get(f"/api/finogrid/agents/{agent_id}/kya")
    assert resp.status_code == 200
    assert resp.json()["kya_level"] == "basic"

    # 5. Top up
    resp = await client.post(f"/api/finogrid/agents/{agent_id}/topup", json={
        "amount_usdc": 100.0,
        "deposit_tx_hash": "0xdemodeposit123",
    })
    assert resp.status_code == 200
    assert resp.json()["new_balance"] == 100.0

    # 6. Create closed-loop wallet
    resp = await client.post(f"/api/finogrid/agents/{agent_id}/wallets", json={
        "label": "test-wallet",
        "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f7bD18",
        "loop_type": "closed",
        "max_per_tx_usdc": 1.00,
        "max_daily_usdc": 10.00,
    })
    assert resp.status_code == 200
    wallet_id = resp.json()["wallet_id"]

    # 7. Create payment intent
    resp = await client.post("/api/finogrid/payment-intents", json={
        "payer_wallet_id": wallet_id,
        "amount_usdc": 0.25,
        "intent_description": "Pay for AI inference",
        "intent_category": "compute",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    })
    assert resp.status_code == 200
    intent_id = resp.json()["payment_intent_id"]

    # 8. Execute micropay
    resp = await client.post("/api/finogrid/micropay", json={
        "idempotency_key": f"test-{uid}-pay-1",
        "payer_wallet_id": wallet_id,
        "payee_address": "0x1111111111111111111111111111111111111111",
        "amount_usdc": 0.25,
        "payment_intent_id": intent_id,
    })
    assert resp.status_code == 200
    tx = resp.json()
    assert tx["status"] == "settled_offchain"
    assert len(tx["gates_passed"]) > 5

    # 9. Idempotency check
    resp = await client.post("/api/finogrid/micropay", json={
        "idempotency_key": f"test-{uid}-pay-1",
        "payer_wallet_id": wallet_id,
        "payee_address": "0x1111111111111111111111111111111111111111",
        "amount_usdc": 0.25,
        "payment_intent_id": intent_id,
    })
    assert resp.status_code == 200
    assert "cached" in str(resp.json()["gates_passed"]).lower()

    # 10. Check balance
    resp = await client.get(f"/api/finogrid/agents/{agent_id}/balance")
    assert resp.status_code == 200
    balance = resp.json()
    assert balance["prefund_balance_usdc"] == 99.75
    assert len(balance["recent_entries"]) > 0


@pytest.mark.asyncio
async def test_micropay_insufficient_funds(client):
    """Test rejection when balance is insufficient."""
    uid = uuid.uuid4().hex[:6]
    resp = await client.post(f"/api/finogrid/clients?name=PC_{uid}&email=p_{uid}@test.com")
    client_id = resp.json()["client_id"]

    resp = await client.post("/api/finogrid/agents", json={
        "name": f"poor-{uid}",
        "owner_client_id": client_id,
    })
    agent_id = resp.json()["agent_account_id"]

    # KYA
    await client.post(f"/api/finogrid/agents/{agent_id}/kya", json={
        "agent_purpose": "test", "declared_use_case": "general",
        "agent_owner_attestation": "test",
    })
    await client.get(f"/api/finogrid/agents/{agent_id}/kya")

    # Create open-loop wallet (no balance)
    resp = await client.post(f"/api/finogrid/agents/{agent_id}/wallets", json={
        "label": "empty-wallet",
        "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f7bD18",
        "loop_type": "open",
        "max_per_tx_usdc": 100.0,
        "max_daily_usdc": 1000.0,
    })
    wallet_id = resp.json()["wallet_id"]

    # Try to pay with 0 balance
    resp = await client.post("/api/finogrid/micropay", json={
        "idempotency_key": f"insuf-{uuid.uuid4().hex[:8]}",
        "payer_wallet_id": wallet_id,
        "payee_address": "0x1111111111111111111111111111111111111111",
        "amount_usdc": 0.50,
    })
    assert resp.status_code == 400
    assert "insufficient" in resp.json()["detail"].lower() or "exceed" in resp.json()["detail"].lower() or "gate" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_micropay_kya_required(client):
    """Test that unverified agent cannot create wallet."""
    uid = uuid.uuid4().hex[:6]
    resp = await client.post(f"/api/finogrid/clients?name=UC_{uid}&email=u_{uid}@test.com")
    client_id = resp.json()["client_id"]

    resp = await client.post("/api/finogrid/agents", json={
        "name": f"unv-{uid}",
        "owner_client_id": client_id,
    })
    agent_id = resp.json()["agent_account_id"]

    # Top up but skip KYA — try to create wallet directly
    resp = await client.post(f"/api/finogrid/agents/{agent_id}/topup", json={
        "amount_usdc": 10.0, "deposit_tx_hash": "0x123",
    })
    resp = await client.post(f"/api/finogrid/agents/{agent_id}/wallets", json={
        "label": "w", "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f7bD18",
        "loop_type": "open",
    })
    assert resp.status_code == 400  # KYA required


@pytest.mark.asyncio
async def test_b2b_payout_batch(client):
    """Test B2B payout batch across corridors."""
    uid = uuid.uuid4().hex[:6]
    resp = await client.post(f"/api/finogrid/clients?name=PR_{uid}&email=pr_{uid}@test.com")
    client_id = resp.json()["client_id"]

    resp = await client.post("/api/finogrid/batches", json={
        "client_id": client_id,
        "reference": f"PAYROLL-{uid}",
        "tasks": [
            {
                "corridor_code": "BR", "recipient_name": "Joao Silva",
                "amount_usd": 500.0, "preferred_asset": "USDC",
                "preferred_mode": "wallet",
                "beneficiary_data": {"cpf_cnpj": "123.456.789-00"},
            },
            {
                "corridor_code": "IN", "recipient_name": "Priya Sharma",
                "amount_usd": 300.0, "preferred_asset": "USDC",
                "preferred_mode": "fiat",
                "beneficiary_data": {"vpa": "priya@upi"},
            },
        ],
    })
    assert resp.status_code == 200
    batch = resp.json()
    assert batch["task_count"] == 2
    assert batch["completed_count"] == 2
    assert batch["status"] == "completed"

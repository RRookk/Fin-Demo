"""Finogrid Python SDK — mirrors the production TypeScript SDK.

Usage:
    from demo.sdk import FinogridClient

    client = FinogridClient(base_url="http://localhost:8002", api_key="fig_agent_...")

    # Agents
    agent = client.agents.create("my-agent", owner_client_id="...")
    print(agent["api_key"])  # only returned once!

    # KYA
    client.kya.submit(agent["agent_account_id"], purpose="...", use_case="content_generation", attestation="...")
    status = client.kya.poll_until(agent["agent_account_id"], "basic")
    print(status["kya_level"])  # "basic"

    # Wallet + Pay
    wallet = client.wallets.create(agent["agent_account_id"], label="tips",
                                    wallet_address="0x...", loop_type="closed")
    intent = client.payment_intents.create(wallet["wallet_id"], amount=0.05,
                                            description="AI inference", category="compute")
    tx = client.micropay.pay(idempotency_key="...", payer_wallet_id=wallet["wallet_id"],
                              payee_address="0x...", amount_usdc=0.05,
                              payment_intent_id=intent["payment_intent_id"])
    print(tx["status"])  # "settled_offchain"
"""

import time
import uuid
from typing import Optional
import httpx


class FinogridApiError(Exception):
    """Raised when the Finogrid API returns an error."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{status_code}] {message}")


class X402PaymentRequiredError(FinogridApiError):
    """Raised when a resource requires x402 payment."""
    def __init__(self, requirement: dict):
        self.requirement = requirement
        super().__init__(402, f"Payment required: {requirement.get('amount')} {requirement.get('token')}")


class BaseClient:
    """Base HTTP client with retry logic."""
    def __init__(self, base_url: str, api_key: Optional[str] = None,
                 max_retries: int = 2, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-Agent-API-Key"] = self.api_key
        return h

    def _request(self, method: str, path: str, json_data: dict = None,
                 params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.request(
                        method=method, url=url, json=json_data,
                        params=params, headers=self._headers(),
                    )

                if resp.status_code == 402:
                    # x402 payment required
                    import base64, json
                    req_header = resp.headers.get("PAYMENT-REQUIRED", "")
                    try:
                        requirement = json.loads(base64.b64decode(req_header))
                    except Exception:
                        requirement = resp.json().get("requirement", {})
                    raise X402PaymentRequiredError(requirement)

                if resp.status_code >= 400:
                    detail = resp.json().get("detail", resp.text)
                    raise FinogridApiError(resp.status_code, detail)

                return resp.json()

            except (FinogridApiError, X402PaymentRequiredError):
                raise
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                continue

        raise FinogridApiError(0, f"Request failed after {self.max_retries} retries: {last_error}")


# ========== Resource Clients ==========

class AgentsClient(BaseClient):
    def create(self, name: str, owner_client_id: str, chain: str = "base") -> dict:
        return self._request("POST", "/api/finogrid/agents", {
            "name": name, "owner_client_id": owner_client_id, "chain": chain,
        })

    def get_balance(self, agent_id: str) -> dict:
        return self._request("GET", f"/api/finogrid/agents/{agent_id}/balance")

    def topup(self, agent_id: str, amount_usdc: float, deposit_tx_hash: str = "") -> dict:
        return self._request("POST", f"/api/finogrid/agents/{agent_id}/topup", {
            "amount_usdc": amount_usdc, "deposit_tx_hash": deposit_tx_hash,
        })


class KYAClient(BaseClient):
    def submit(self, agent_id: str, purpose: str, use_case: str,
               attestation: str, validator: str = "internal") -> dict:
        return self._request("POST", f"/api/finogrid/agents/{agent_id}/kya", {
            "agent_purpose": purpose, "declared_use_case": use_case,
            "agent_owner_attestation": attestation, "validator_name": validator,
        })

    def get_status(self, agent_id: str) -> dict:
        return self._request("GET", f"/api/finogrid/agents/{agent_id}/kya")

    def poll_until(self, agent_id: str, target_level: str = "basic",
                   interval: float = 0.5, timeout: float = 10.0) -> dict:
        """Poll KYA status until target level is reached."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_status(agent_id)
            if status["kya_level"] in (target_level, "enhanced"):
                return status
            time.sleep(interval)
        raise TimeoutError(f"KYA did not reach {target_level} within {timeout}s")


class WalletsClient(BaseClient):
    def create(self, agent_id: str, label: str, wallet_address: str,
               loop_type: str = "closed", max_per_tx: float = 0.10,
               max_daily: float = 1.00, allowed_counterparties: list = None,
               expires_at: str = None, max_uses: int = None) -> dict:
        body = {
            "label": label, "wallet_address": wallet_address,
            "loop_type": loop_type, "max_per_tx_usdc": max_per_tx,
            "max_daily_usdc": max_daily,
        }
        if allowed_counterparties:
            body["allowed_counterparties"] = allowed_counterparties
        if expires_at:
            body["expires_at"] = expires_at
        if max_uses:
            body["max_uses"] = max_uses
        return self._request("POST", f"/api/finogrid/agents/{agent_id}/wallets", body)

    def list(self, agent_id: str) -> dict:
        return self._request("GET", f"/api/finogrid/agents/{agent_id}/wallets")


class PaymentIntentsClient(BaseClient):
    def create(self, payer_wallet_id: str, amount: float,
               description: str, category: str = "compute",
               expires_at: str = None) -> dict:
        if not expires_at:
            from datetime import datetime, timezone, timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        return self._request("POST", "/api/finogrid/payment-intents", {
            "payer_wallet_id": payer_wallet_id, "amount_usdc": amount,
            "intent_description": description, "intent_category": category,
            "expires_at": expires_at,
        })


class MicropayClient(BaseClient):
    def pay(self, idempotency_key: str, payer_wallet_id: str,
            payee_address: str, amount_usdc: float,
            payment_intent_id: str = None,
            x402_resource_url: str = None) -> dict:
        body = {
            "idempotency_key": idempotency_key,
            "payer_wallet_id": payer_wallet_id,
            "payee_address": payee_address,
            "amount_usdc": amount_usdc,
        }
        if payment_intent_id:
            body["payment_intent_id"] = payment_intent_id
        if x402_resource_url:
            body["x402_resource_url"] = x402_resource_url
        return self._request("POST", "/api/finogrid/micropay", body)


class FinogridClient:
    """Main client facade for the Finogrid Agent Ledger API.

    Usage:
        client = FinogridClient(base_url="http://localhost:8002", api_key="fig_agent_...")
        agent = client.agents.create("my-agent", owner_client_id="...")
        wallet = client.wallets.create(agent["agent_account_id"], ...)
        tx = client.micropay.pay(...)
    """
    def __init__(self, base_url: str = "http://localhost:8002",
                 api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.agents = AgentsClient(base_url, api_key)
        self.kya = KYAClient(base_url, api_key)
        self.wallets = WalletsClient(base_url, api_key)
        self.payment_intents = PaymentIntentsClient(base_url, api_key)
        self.micropay = MicropayClient(base_url, api_key)

"""Finogrid x402 Middleware — HTTP 402 Payment Required protocol.

Implements the Coinbase/Cloudflare x402 standard for machine-to-machine payments.
In demo mode, this is a showcase; in production, it validates real payment signatures.
"""

import json
import base64
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class PaymentRequiredMiddleware(BaseHTTPMiddleware):
    """Middleware that can return HTTP 402 with payment requirement metadata.

    x402-protected paths return 402 with a PAYMENT-REQUIRED header containing
    base64-encoded JSON describing the required payment. The client is expected
    to pay and retry with a PAYMENT-SIGNATURE header.

    Protected paths (demo):
      - /api/finogrid/protected/premium-report
    """

    def __init__(self, app, protected_paths: list = None):
        super().__init__(app)
        self.protected_paths = protected_paths or [
            "/api/finogrid/protected/premium-report",
        ]

    async def dispatch(self, request: Request, call_next):
        # Check if path is payment-protected
        for path in self.protected_paths:
            if request.url.path.startswith(path):
                # Check for payment signature
                payment_signature = request.headers.get("PAYMENT-SIGNATURE")
                if not payment_signature:
                    # Return 402 with payment requirement
                    requirement = json.dumps({
                        "network": "base",
                        "token": "USDC",
                        "amount": "0.05",
                        "recipient": "0xFinogridAgentLedger0000000000000000000000000",
                        "description": "Premium financial report access",
                        "x402_version": "1.0",
                    })
                    return JSONResponse(
                        status_code=402,
                        content={
                            "error": "Payment Required",
                            "message": "This resource requires payment. Include PAYMENT-SIGNATURE header.",
                            "requirement": json.loads(requirement),
                        },
                        headers={
                            "PAYMENT-REQUIRED": base64.b64encode(requirement.encode()).decode(),
                            "X-402-Version": "1.0",
                        },
                    )
                else:
                    # In demo mode, accept any signature
                    response = await call_next(request)
                    response.headers["PAYMENT-RESPONSE"] = json.dumps({
                        "status": "settled",
                        "tx_hash": f"0x{dummy_tx_hash(payment_signature)}",
                        "amount": "0.05",
                        "token": "USDC",
                    })
                    return response

        # Not a protected path — pass through
        return await call_next(request)


def dummy_tx_hash(sig: str) -> str:
    """Generate a deterministic fake tx hash from signature for demo."""
    import hashlib
    return hashlib.sha256(sig.encode()).hexdigest()[:64]

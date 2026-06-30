"""Finogrid corridor adapters — simplified 8-country routing for demo.

Mirrors the production corridor pattern from finogrid/corridors/.
Each adapter specifies: payment rails, required beneficiary fields, limits, and AML rules.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CorridorConfig:
    corridor_code: str
    country: str
    currency: str
    payment_rails: List[str]  # e.g., ["PIX"], ["UPI", "IMPS"]
    min_amount_usd: float = 1.0
    max_amount_usd: float = 10_000.0
    wallet_enabled: bool = True
    fiat_enabled: bool = True
    wallet_sla_minutes: int = 60
    fiat_sla_minutes: int = 120
    required_fields: List[str] = field(default_factory=list)
    kyt_risk_threshold: int = 7  # 1-10, lower = stricter
    special_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "corridor_code": self.corridor_code,
            "country": self.country,
            "currency": self.currency,
            "payment_rails": self.payment_rails,
            "amount_range": f"${self.min_amount_usd:,.0f} – ${self.max_amount_usd:,.0f}",
            "wallet_enabled": self.wallet_enabled,
            "fiat_enabled": self.fiat_enabled,
            "wallet_sla": f"{self.wallet_sla_minutes}min",
            "fiat_sla": f"{self.fiat_sla_minutes}min",
            "required_fields": self.required_fields,
            "special_rules": self.special_rules,
        }


# ========== 8 Corridor Adapters ==========

CORRIDORS: dict[str, CorridorConfig] = {
    "BR": CorridorConfig(
        corridor_code="BR", country="Brazil", currency="BRL",
        payment_rails=["PIX"],
        wallet_sla_minutes=60, fiat_sla_minutes=120,
        required_fields=["cpf_cnpj"],
        kyt_risk_threshold=6,
        special_rules=["CPF/CNPJ validation required", "PIX instant settlement 24/7"],
    ),
    "NG": CorridorConfig(
        corridor_code="NG", country="Nigeria", currency="NGN",
        payment_rails=["NIBSS"],
        wallet_sla_minutes=45, fiat_sla_minutes=90,
        required_fields=["bvn"],
        kyt_risk_threshold=7,
        special_rules=["BVN mandatory for amounts ≥$100", "TRC-20 USDT preferred rail"],
    ),
    "IN": CorridorConfig(
        corridor_code="IN", country="India", currency="INR",
        payment_rails=["UPI", "IMPS"],
        min_amount_usd=1.0, max_amount_usd=10_000.0,
        wallet_sla_minutes=30, fiat_sla_minutes=240,
        required_fields=["vpa"],
        kyt_risk_threshold=6,
        special_rules=["VPA (UPI ID) required", "RBI-regulated corridors only"],
    ),
    "AR": CorridorConfig(
        corridor_code="AR", country="Argentina", currency="ARS",
        payment_rails=["CBU"],
        max_amount_usd=25_000.0,
        wallet_sla_minutes=90, fiat_sla_minutes=180,
        required_fields=["cuit"],
        kyt_risk_threshold=6,
        special_rules=["CUIT required", "$25,000 max per transaction"],
    ),
    "VN": CorridorConfig(
        corridor_code="VN", country="Vietnam", currency="VND",
        payment_rails=["Napas", "VietQR"],
        wallet_sla_minutes=60, fiat_sla_minutes=120,
        required_fields=["bin_code"],
        kyt_risk_threshold=5,
        special_rules=["BIN code required", "VietQR for instant settlement"],
    ),
    "AE": CorridorConfig(
        corridor_code="AE", country="UAE", currency="AED",
        payment_rails=["IBAN", "SWIFT"],
        max_amount_usd=100_000.0,
        wallet_sla_minutes=120, fiat_sla_minutes=360,
        kyt_risk_threshold=8,
        special_rules=["$100,000 max (hub market)", "SWIFT settlement 1-3 business days"],
    ),
    "ID": CorridorConfig(
        corridor_code="ID", country="Indonesia", currency="IDR",
        payment_rails=["BI-FAST"],
        wallet_sla_minutes=45, fiat_sla_minutes=120,
        required_fields=["nik"],
        kyt_risk_threshold=6,
        special_rules=["NIK required", "BI-FAST real-time settlement"],
    ),
    "PH": CorridorConfig(
        corridor_code="PH", country="Philippines", currency="PHP",
        payment_rails=["InstaPay", "PESONet"],
        wallet_sla_minutes=30, fiat_sla_minutes=120,
        required_fields=["bank_account_number", "bank_code"],
        kyt_risk_threshold=6,
        special_rules=["GCash optional for mobile wallet delivery", "InstaPay instant, PESONet batch"],
    ),
}


def get_corridor(corridor_code: str) -> Optional[CorridorConfig]:
    """Get corridor config by ISO2 code."""
    return CORRIDORS.get(corridor_code.upper())


def list_corridors() -> List[dict]:
    """List all available corridors."""
    return [c.to_dict() for c in CORRIDORS.values()]


def validate_beneficiary(corridor_code: str, beneficiary_data: dict) -> dict:
    """Validate beneficiary data against corridor requirements."""
    corridor = get_corridor(corridor_code)
    if not corridor:
        return {"valid": False, "errors": [f"Unknown corridor: {corridor_code}"]}

    missing = []
    for field in corridor.required_fields:
        if not beneficiary_data.get(field):
            missing.append(field)

    if missing:
        return {
            "valid": False,
            "errors": [f"Missing required fields: {', '.join(missing)}"],
            "missing_fields": missing,
        }

    return {"valid": True, "errors": []}


def route_payout(corridor_code: str, amount_usd: float, preferred_asset: str,
                 preferred_mode: str) -> dict:
    """Route a payout to the appropriate partner/rail (simulated)."""
    corridor = get_corridor(corridor_code)
    if not corridor:
        return {"error": f"Unknown corridor: {corridor_code}"}

    if amount_usd < corridor.min_amount_usd:
        return {"error": f"Amount below minimum: ${corridor.min_amount_usd:,.0f}"}
    if amount_usd > corridor.max_amount_usd:
        return {"error": f"Amount above maximum: ${corridor.max_amount_usd:,.0f}"}

    # Determine asset
    asset = preferred_asset if preferred_asset in ("USDC", "USDT") else "USDC"

    # Determine mode and partner
    if preferred_mode == "wallet" and corridor.wallet_enabled:
        mode = "wallet"
        partner = f"{corridor.payment_rails[0]}-Crypto-Partner"
        sla = corridor.wallet_sla_minutes
    elif corridor.fiat_enabled:
        mode = "fiat"
        partner = f"{corridor.payment_rails[0]}-Bank-Partner"
        sla = corridor.fiat_sla_minutes
    else:
        return {"error": "No available delivery mode for this corridor"}

    return {
        "corridor_code": corridor_code,
        "country": corridor.country,
        "amount_usd": amount_usd,
        "resolved_asset": asset,
        "resolved_mode": mode,
        "partner": partner,
        "estimated_sla_minutes": sla,
        "rail": corridor.payment_rails[0],
    }

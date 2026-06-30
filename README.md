# Fin Demo

A lightweight API demo showcasing **Fin-train** (Financial LLM Fine-Tuning) and **Finogrid** (B2B Stablecoin Payout + Agent-to-Agent Micro-Transactions).

> **Zero config, zero GPU** — runs locally with SQLite and simulated AI inference.

[中文文档](README_CN.md)

---

## What is Fin?

Fin is a dual-layer financial infrastructure project:

| Module | Purpose | Demo Status |
|--------|---------|-------------|
| **Fin-train** | Financial LLM fine-tuning framework (LoRA, sentiment analysis, stock forecasting, RAG) | ✅ Simulated inference |
| **Finogrid** | B2B stablecoin payouts across 8 countries + A2A agent micropay with KYA compliance | ✅ Full flow with SQLite |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch
python run.py

# 3. Open API docs
open http://localhost:8000/docs
```

That's it! The database is auto-created, and all AI is simulated.

---

## Architecture

```
fin-demo/
├── demo/
│   ├── fin_train/          # Fin-train API (sentiment, forecaster, RAG)
│   │   ├── sentiment.py    #    Keyword-based sentiment analysis
│   │   ├── forecaster.py   #    yfinance data + structured analysis
│   │   ├── rag.py          #    Simulated multi-source retrieval
│   │   ├── prompts.py      #    Original Fin-train prompt templates
│   │   └── routes.py       #    FastAPI endpoints
│   │
│   ├── finogrid/           # Finogrid API (agent ledger + B2B payout)
│   │   ├── models.py       #    Data models (Agent, Wallet, Intent, MicroTx)
│   │   ├── agent_ledger.py #    10-gate micropay compliance engine
│   │   ├── corridors.py    #    8 country corridor adapters
│   │   ├── payout.py       #    B2B batch payout pipeline
│   │   ├── midware.py     #    x402 HTTP 402 middleware
│   │   └── routes.py       #    FastAPI endpoints
│   │
│   └── sdk/                # Python SDK
│       └── client.py       #    FinogridClient with resource clients
│
├── tests/                  # Pytest async tests
└── run.py                  # One-click launcher
```

---

## API Endpoints

### Fin-train (Financial AI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/fin-train/sentiment` | Analyze financial text sentiment |
| `POST` | `/api/fin-train/forecast` | Generate stock price forecast (real yfinance data) |
| `POST` | `/api/fin-train/rag` | Financial Q&A with simulated retrieval |

### Finogrid (Agent Payments)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/finogrid/clients` | Register B2B client |
| `POST` | `/api/finogrid/agents` | Register AI agent → get API key |
| `POST` | `/api/finogrid/agents/{id}/kya` | Submit KYA verification |
| `GET`  | `/api/finogrid/agents/{id}/kya` | Poll KYA (auto-approves in demo) |
| `POST` | `/api/finogrid/agents/{id}/topup` | Add USDC balance |
| `POST` | `/api/finogrid/agents/{id}/wallets` | Create wallet (open/closed loop) |
| `POST` | `/api/finogrid/payment-intents` | Reserve funds (closed-loop) |
| `POST` | `/api/finogrid/micropay` | Execute micropayment (10-gate compliance!) |
| `GET`  | `/api/finogrid/agents/{id}/balance` | Get balance + ledger entries |
| `POST` | `/api/finogrid/batches` | B2B payout batch (v1 pipeline) |
| `GET`  | `/api/finogrid/corridors` | List all 8 payment corridors |

---

## Demo Walkthrough

### 1. Stock Sentiment Analysis

```bash
curl -X POST http://localhost:8000/api/fin-train/sentiment \
  -H "Content-Type: application/json" \
  -d '{"text": "Apple reported record revenue of $94.9B, up 6% YoY. Services grew 14% to $25B."}'
```

**Response:**
```json
{
  "sentiment": "positive",
  "confidence": 0.82,
  "explanation": [
    "Apple reported record revenue of $94.9B, up 6% YoY.",
    "Services grew 14% to $25B."
  ],
  "model_info": {
    "model": "Fin-train-Sentiment-LoRA",
    "base_model": "Llama-2-7B",
    "note": "[DEMO MODE] Simulated inference"
  }
}
```

### 2. Stock Forecast (real data!)

```bash
curl -X POST http://localhost:8000/api/fin-train/forecast \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "n_weeks": 2}'
```

Gets real price history from yfinance and generates a structured analyst report:

```json
{
  "symbol": "AAPL",
  "company_name": "Apple Inc.",
  "current_price": 195.30,
  "positive_developments": [
    "AAPL demonstrated strong momentum with a 5.2% gain.",
    "Trading volume above average indicates strong participation."
  ],
  "potential_concerns": [
    "After significant rally, short-term profit-taking may occur.",
    "Technical indicators may signal overbought conditions."
  ],
  "prediction": "↑ Moderately Bullish — expected 1.8% upside next week",
  "analysis": "Apple has demonstrated strong price performance..."
}
```

### 3. Full Agent Micropay Flow

```python
from demo.sdk import FinogridClient
import uuid

client = FinogridClient(base_url="http://localhost:8000")

# 1. Create client + agent
c = client.agents.create("my-agent", owner_client_id="...")
agent_id = c["agent_account_id"]
api_key = c["api_key"]  # store this!

# 2. KYA (auto-approves in demo)
client.kya.submit(agent_id, "Payment agent for AI services", "content_generation", "I own this agent")
status = client.kya.poll_until(agent_id, "basic")
print(f"KYA: {status['kya_level']}")  # basic

# 3. Add funds
client.agents.topup(agent_id, 100.0)

# 4. Create closed-loop wallet
w = client.wallets.create(agent_id, "compute-payments",
    wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f7bD18",
    loop_type="closed")

# 5. Reserve payment intent
intent = client.payment_intents.create(w["wallet_id"], 0.05,
    "GPT-4 inference — 50K tokens", "compute")

# 6. Execute payment (10-gate compliance!)
tx = client.micropay.pay(
    idempotency_key=str(uuid.uuid4()),
    payer_wallet_id=w["wallet_id"],
    payee_address="0xPayee0000000000000000000000000000000000",
    amount_usdc=0.05,
    payment_intent_id=intent["payment_intent_id"],
)

print(f"Status: {tx['status']}")  # settled_offchain
print(f"Gates passed: {len(tx['gates_passed'])}")  # 10
```

---

## The 10-Gate Compliance Sequence

Every micropayment passes through 10 compliance gates:

1. **Idempotency** — Duplicate detection via caller-supplied key
2. **KYA + Wallet Ownership** — Agent must be verified, wallet active
3. **Loop Type / Intent Validation** — Closed-loop requires valid PaymentIntent
4. **Counterparty Allowlist** — Optional per-wallet address filtering
5. **Per-Transaction Cap** — `max_per_tx_usdc` enforcement
6. **Wallet Daily Velocity** — `max_daily_usdc` with auto-reset
7. **KYA-Level Aggregate** — $1/day (basic) or $100/day (enhanced) across all wallets
8. **Wallet Expiry / Max Uses** — Auto-expiry and use-count limits
9. **Balance Sufficiency** — Available balance check
10. **Off-Chain Settlement** — Atomic balance update + double-entry ledger

---

## Supported Payment Corridors

| Code | Country | Rails | Wallet SLA |
|------|---------|-------|-----------|
| BR | 🇧🇷 Brazil | PIX | 60 min |
| NG | 🇳🇬 Nigeria | NIBSS | 45 min |
| IN | 🇮🇳 India | UPI, IMPS | 30 min |
| AR | 🇦🇷 Argentina | CBU | 90 min |
| VN | 🇻🇳 Vietnam | Napas, VietQR | 60 min |
| AE | 🇦🇪 UAE | IBAN, SWIFT | 120 min |
| ID | 🇮🇩 Indonesia | BI-FAST | 45 min |
| PH | 🇵🇭 Philippines | InstaPay, PESONet | 30 min |

---

## Running Tests

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

---

## What's Real vs. Demo

| Component | Real | Demo |
|-----------|------|------|
| Fin-train LoRA model | GPU + 13GB checkpoint | Simulated keyword analysis |
| Stock price data | yfinance API | ✅ Same (yfinance) |
| Market sentiment | Adanos API (Reddit/X/Polymarket) | Simulated |
| News retrieval | Multi-source scrapers (Reuters, Bloomberg) | Simulated knowledge base |
| Database | AlloyDB (PostgreSQL) | SQLite |
| On-chain settlement | Base L2 (USDC) | Simulated |
| KYA validation | Sardine / Persona / Chainalysis | Auto-approve (demo) |
| Compliance screening | Chainalysis KYT | Simulated |
| Message queue | GCP Pub/Sub | Direct |
| **10-gate compliance** | ✅ Same logic | ✅ **Same logic!** |
| **Corridor adapter pattern** | ✅ Same pattern | ✅ **Same pattern!** |
| **Double-entry ledger** | ✅ Same | ✅ **Same!** |
| **x402 protocol** | ✅ Same | ✅ **Same middleware!** |

---

## Tech Stack

- **FastAPI** — Modern async Python web framework
- **SQLAlchemy 2.0** — Async ORM with SQLite
- **Pydantic v2** — Type-safe request/response validation
- **yfinance** — Real-time stock data
- **httpx** — Async HTTP client

---

## License

MIT — see [LICENSE](../Fin/LICENSE) from the original Fin project.

---

*Built as a demo companion to the Fin project. For production deployment, see the full [Finogrid](https://github.com/your-username/fin) repository.*

"""Finogrid — B2B Stablecoin Payout + Agent-to-Agent Micro-Transaction Platform Demo.

Modules:
- models: SQLAlchemy data models (AgentAccount, Wallet, PaymentIntent, MicroTransaction, etc.)
- database: SQLite async database setup
- agent_ledger: Core business logic (agent registration, KYA, wallets, micropay, 10-gate compliance)
- corridors: 8 country corridor adapters (simplified for demo)
- payout: B2B payout flow simulation
- middleware: x402 HTTP 402 payment-walling middleware
- routes: FastAPI router with all endpoints
"""

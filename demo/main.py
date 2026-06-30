"""Fin Demo — Main FastAPI application.

Mounts Fin-train (port 8001) and Finogrid (port 8002) as separate sub-applications.
Can also run as a combined app on a single port for convenience.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from demo.fin_train.routes import router as fin_train_router
from demo.finogrid.routes import router as finogrid_router
from demo.finogrid.midware import PaymentRequiredMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: initialize database."""
    from demo.finogrid.database import init_db
    await init_db()
    print("[Fin Demo] Database initialized (SQLite)")
    yield


def create_fin_train_app() -> FastAPI:
    """Create the Fin-train API app (port 8001)."""
    app = FastAPI(
        title="Fin-train API",
        description="Financial LLM Fine-Tuning Framework — Sentiment, Forecaster, RAG",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(fin_train_router)

    @app.get("/")
    async def root():
        return {
            "service": "Fin-train API",
            "version": "0.1.0",
            "docs": "/docs",
            "endpoints": {
                "sentiment": "POST /api/fin-train/sentiment",
                "forecast": "POST /api/fin-train/forecast",
                "rag": "POST /api/fin-train/rag",
                "health": "GET /api/fin-train/health",
            },
        }

    return app


def create_finogrid_app() -> FastAPI:
    """Create the Finogrid API app (port 8002)."""
    app = FastAPI(
        title="Finogrid API",
        description="B2B Stablecoin Payout + Agent-to-Agent Micro-Transaction Platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Add x402 payment middleware
    app.add_middleware(PaymentRequiredMiddleware)
    app.include_router(finogrid_router)

    @app.get("/")
    async def root():
        return {
            "service": "Finogrid API",
            "version": "0.1.0",
            "docs": "/docs",
            "core_flow": [
                "1. POST /api/finogrid/clients — Register B2B client",
                "2. POST /api/finogrid/agents — Register AI agent",
                "3. POST /api/finogrid/agents/{id}/kya — Submit KYA",
                "4. GET  /api/finogrid/agents/{id}/kya — Poll KYA (auto-approves in demo)",
                "5. POST /api/finogrid/agents/{id}/topup — Add USDC balance",
                "6. POST /api/finogrid/agents/{id}/wallets — Create wallet",
                "7. POST /api/finogrid/payment-intents — Reserve funds (closed-loop)",
                "8. POST /api/finogrid/micropay — Execute payment (10-gate compliance)",
                "9. GET  /api/finogrid/agents/{id}/balance — Check balance + ledger",
            ],
        }

    return app


def create_combined_app() -> FastAPI:
    """Create a combined app with both Fin-train and Finogrid (single port)."""
    app = FastAPI(
        title="Fin Demo",
        description="Fin-train & Finogrid — Financial AI + Agent Payment Infrastructure Demo",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(fin_train_router)
    app.include_router(finogrid_router)

    @app.get("/")
    async def root():
        return {
            "project": "Fin Demo",
            "modules": {
                "fin_train": {
                    "description": "Financial LLM Fine-Tuning Framework",
                    "endpoints": ["/api/fin-train/sentiment", "/api/fin-train/forecast", "/api/fin-train/rag"],
                },
                "finogrid": {
                    "description": "B2B Stablecoin Payout + A2A Micro-Transaction Platform",
                    "endpoints": ["/api/finogrid/agents", "/api/finogrid/micropay", "/api/finogrid/batches"],
                },
            },
            "docs": "/docs",
            "note": "This is a demo. All AI inference is simulated. Database is SQLite.",
        }

    return app

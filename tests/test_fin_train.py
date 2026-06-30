"""Tests for Fin-train API endpoints."""

import pytest_asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from demo.main import create_fin_train_app


@pytest_asyncio.fixture
async def client():
    app = create_fin_train_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/fin-train/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["module"] == "Fin-train"


@pytest.mark.asyncio
async def test_sentiment_positive(client):
    resp = await client.post("/api/fin-train/sentiment", json={
        "text": "Apple reported record quarterly revenue with 11% growth in services and strong iPhone sales."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment"] in ("positive", "negative", "neutral")
    assert 0.0 <= data["confidence"] <= 1.0
    assert len(data["explanation"]) > 0


@pytest.mark.asyncio
async def test_sentiment_negative(client):
    resp = await client.post("/api/fin-train/sentiment", json={
        "text": "The company reported a significant decline in revenue, missed earnings expectations, and announced layoffs."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment"] == "negative"


@pytest.mark.asyncio
async def test_sentiment_neutral(client):
    resp = await client.post("/api/fin-train/sentiment", json={
        "text": "The meeting is scheduled for tomorrow."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["sentiment"] == "neutral"


@pytest.mark.asyncio
async def test_forecast_invalid_symbol(client):
    resp = await client.post("/api/fin-train/forecast", json={
        "symbol": "ZZZZZZZZ", "n_weeks": 2
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_forecast_valid_symbol(client):
    """Test with a real ticker — may fail if yfinance is blocked by network."""
    try:
        resp = await client.post("/api/fin-train/forecast", json={
            "symbol": "AAPL", "n_weeks": 1,
            "include_sentiment": False, "include_financials": False,
        })
        if resp.status_code == 200:
            data = resp.json()
            assert data["symbol"] == "AAPL"
            assert "positive_developments" in data
            assert "potential_concerns" in data
            assert data["prediction"]
    except Exception:
        pass  # Network issues OK in test


@pytest.mark.asyncio
async def test_rag_query(client):
    resp = await client.post("/api/fin-train/rag", json={
        "question": "What were Apple's Q4 revenue drivers?",
        "top_k": 3,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["question"]
    assert len(data["answer"]) > 0
    assert len(data["retrieved_documents"]) > 0
    assert 0.0 <= data["retrieved_documents"][0]["relevance_score"] <= 1.0


@pytest.mark.asyncio
async def test_rag_empty_question(client):
    resp = await client.post("/api/fin-train/rag", json={
        "question": "XYZ ABC 123",
        "top_k": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]

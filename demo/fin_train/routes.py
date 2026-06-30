"""Fin-train API routes — sentiment analysis, stock forecasting, RAG."""

from fastapi import APIRouter, HTTPException
from demo.fin_train.schemas import (
    SentimentRequest, SentimentResponse,
    ForecasterRequest, ForecasterResponse,
    RAGRequest, RAGResponse,
)
from demo.fin_train.sentiment import analyze_sentiment
from demo.fin_train.forecaster import generate_forecast
from demo.fin_train.rag import retrieve_and_answer

router = APIRouter(prefix="/api/fin-train", tags=["Fin-train"])


@router.get("/health")
async def health():
    return {"status": "ok", "module": "Fin-train", "mode": "demo"}


@router.post("/sentiment", response_model=SentimentResponse)
async def sentiment_analysis(req: SentimentRequest):
    """Analyze financial text sentiment using Fin-train Sentiment Analysis.

    Simulates a LoRA-finetuned Llama-2-7B model trained on financial sentiment data.
    In production, this uses the actual model checkpoint from HuggingFace Hub.
    """
    result = analyze_sentiment(req.text)
    return SentimentResponse(
        sentiment=result["sentiment"],
        confidence=result["confidence"],
        explanation=result["explanation"],
    )


@router.post("/forecast", response_model=ForecasterResponse)
async def stock_forecast(req: ForecasterRequest):
    """Generate stock price forecast using Fin-train Forecaster.

    Uses real price data from yfinance and simulates the LoRA-finetuned
    Llama-2-7B model's structured analyst report format.
    """
    result = generate_forecast(
        symbol=req.symbol,
        n_weeks=req.n_weeks,
        include_sentiment=req.include_sentiment,
        include_financials=req.include_financials,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return ForecasterResponse(
        symbol=result["symbol"],
        company_name=result["company_name"],
        current_price=result["current_price"],
        period=result["period"],
        price_history=result["price_history"],
        positive_developments=result["positive_developments"],
        potential_concerns=result["potential_concerns"],
        prediction=result["prediction"],
        analysis=result["analysis"],
    )


@router.post("/rag", response_model=RAGResponse)
async def rag_query(req: RAGRequest):
    """Answer financial questions using Fin-train RAG.

    Simulates multi-source retrieval (Reuters, Bloomberg, SEC filings, etc.) and
    the instruct-Fin-train model for answer generation.
    """
    result = retrieve_and_answer(req.question, top_k=req.top_k)
    return RAGResponse(
        question=result["question"],
        answer=result["answer"],
        retrieved_documents=result["retrieved_documents"],
    )

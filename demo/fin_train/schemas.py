"""Fin-train API schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000,
        description="Financial text to analyze",
        examples=["Apple Inc. reported record quarterly revenue of $89.5 billion."])

class SentimentResponse(BaseModel):
    sentiment: str = Field(..., description="positive, negative, or neutral")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    explanation: list[str] = Field(..., description="Key factors behind the sentiment")
    model_info: dict = Field(default_factory=lambda: {
        "model": "Fin-train-Sentiment-LoRA", "base_model": "Llama-2-7B",
        "adapter_rank": 8, "note": "[DEMO MODE] Simulated inference"})

class ForecasterRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10,
        description="Stock ticker (e.g., AAPL, TSLA)", examples=["AAPL"])
    n_weeks: int = Field(default=2, ge=1, le=4, description="Past weeks of data")
    include_sentiment: bool = Field(default=True, description="Include market sentiment")
    include_financials: bool = Field(default=True, description="Include financials")

class PricePoint(BaseModel):
    date: str = ""
    open_price: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

class ForecasterResponse(BaseModel):
    symbol: str = ""
    company_name: str = ""
    current_price: float = 0.0
    period: dict = Field(default_factory=lambda: {"start_date": "", "end_date": ""})
    price_history: list[PricePoint] = Field(default_factory=list)
    positive_developments: list[str] = Field(default_factory=list)
    potential_concerns: list[str] = Field(default_factory=list)
    prediction: str = ""
    analysis: str = ""
    disclaimer: str = (
        "This is a DEMO prediction. It is NOT financial advice. "
        "Real predictions require a fine-tuned LoRA model on GPU.")
    model_info: dict = Field(default_factory=lambda: {
        "model": "Fin-train-Forecaster-LoRA", "base_model": "Llama-2-7B",
        "adapter_rank": 8, "note": "[DEMO MODE] Simulated inference + real yfinance data"})

class RAGRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000,
        description="Financial question", examples=["What drove Apple's Q4 growth?"])
    top_k: int = Field(default=3, ge=1, le=10)

class RetrievedDocument(BaseModel):
    source: str = ""
    snippet: str = ""
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)

class RAGResponse(BaseModel):
    question: str = ""
    answer: str = ""
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    model_info: dict = Field(default_factory=lambda: {
        "model": "Fin-train-RAG", "retrieval": "multi-source [DEMO] simulated",
        "note": "[DEMO MODE] Simulated retrieval + generation"})

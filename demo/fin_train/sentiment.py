"""Fin-train Sentiment Analysis — simulated LLM inference for demo."""

import re
import random
from demo.fin_train.prompts import SENTIMENT_SYSTEM_PROMPT, SENTIMENT_USER_TEMPLATE


# Keyword-based sentiment analysis (simulates LoRA-finetuned LLM)
POSITIVE_KEYWORDS = [
    "record", "growth", "profit", "increase", "beat", "exceed", "upgrade",
    "bullish", "positive", "strong", "expansion", "surge", "rise", "gain",
    "dividend", "buyback", "innovation", "partnership", "breakthrough",
    "raised guidance", "outperform", "momentum", "recovery", "robust",
]

NEGATIVE_KEYWORDS = [
    "decline", "loss", "debt", "lawsuit", "fine", "downgrade", "bearish",
    "negative", "weak", "layoff", "cut", "drop", "fall", "plunge", "crash",
    "investigation", "fraud", "bankruptcy", "default", "downturn",
    "missed", "below", "warning", "risk", "volatility", "uncertainty",
    "sanction", "tariff", "inflation", "recession",
]


def analyze_sentiment(text: str) -> dict:
    """Simulate Fin-train sentiment analysis with keyword-based scoring."""
    text_lower = text.lower()

    # Count positive/negative signals
    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)

    # Extract explaining phrases
    sentences = re.split(r'[.!?\n]', text)
    pos_reasons = []
    neg_reasons = []

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        for kw in POSITIVE_KEYWORDS:
            if kw in s.lower() and s not in pos_reasons:
                pos_reasons.append(s[:120])
                break
        for kw in NEGATIVE_KEYWORDS:
            if kw in s.lower() and s not in neg_reasons:
                neg_reasons.append(s[:120])
                break

    # Determine sentiment
    total = pos_count + neg_count
    if total == 0:
        sentiment = "neutral"
        confidence = random.uniform(0.55, 0.75)
        explanation = ["No strong positive or negative signals detected.", "The text is primarily factual/neutral in tone."]
    elif pos_count > neg_count * 1.5:
        sentiment = "positive"
        confidence = 0.65 + (pos_count / (total + 3)) * 0.30
        explanation = pos_reasons[:3] if pos_reasons else ["Multiple positive indicators detected."]
    elif neg_count > pos_count * 1.5:
        sentiment = "negative"
        confidence = 0.65 + (neg_count / (total + 3)) * 0.30
        explanation = neg_reasons[:3] if neg_reasons else ["Multiple negative indicators detected."]
    elif pos_count > neg_count:
        sentiment = "positive"
        confidence = 0.55 + (pos_count / (total + 3)) * 0.20
        explanation = (pos_reasons[:2] + neg_reasons[:1]) if pos_reasons else ["Slightly positive bias."]
    elif neg_count > pos_count:
        sentiment = "negative"
        confidence = 0.55 + (neg_count / (total + 3)) * 0.20
        explanation = (neg_reasons[:2] + pos_reasons[:1]) if neg_reasons else ["Slightly negative bias."]
    else:
        sentiment = "neutral"
        confidence = 0.50
        explanation = ["Mixed signals — balanced positive and negative factors."]
        if pos_reasons:
            explanation = pos_reasons[:1] + neg_reasons[:1]

    confidence = min(confidence, 0.95)

    return {
        "sentiment": sentiment,
        "confidence": round(confidence, 2),
        "explanation": explanation or ["Analysis based on keyword pattern matching (demo mode)."],
    }

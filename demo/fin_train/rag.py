"""Fin-train RAG — simulated retrieval-augmented generation for demo."""

import re
from demo.fin_train.prompts import RAG_SYSTEM_PROMPT, RAG_USER_TEMPLATE


# Simulated financial knowledge base
_KNOWLEDGE_BASE = [
    {
        "source": "Apple Q4 2025 Earnings Call Transcript",
        "content": (
            "Apple reported Q4 revenue of $94.9 billion, up 6% year-over-year. "
            "iPhone revenue was $46.2 billion (+5% YoY), Services reached $25.0 billion (+14% YoY), "
            "and Mac revenue was $7.7 billion (+2% YoY). Gross margin was 46.2%. "
            "CEO Tim Cook highlighted strong performance in emerging markets, especially India and Brazil. "
            "CFO Luca Maestri noted that the active installed base reached a new all-time high across all product categories."
        ),
    },
    {
        "source": "Federal Reserve FOMC Statement — September 2025",
        "content": (
            "The Federal Reserve maintained the federal funds rate at 4.25-4.50%. "
            "The Committee noted that inflation has eased but remains somewhat elevated. "
            "The labor market remains strong with unemployment at 3.8%. "
            "The dot plot suggests two rate cuts in 2026, contingent on inflation progress toward the 2% target. "
            "GDP growth is projected at 2.1% for 2025."
        ),
    },
    {
        "source": "Tesla Q3 2025 Delivery Report",
        "content": (
            "Tesla delivered 462,890 vehicles in Q3 2025, beating analyst estimates of 445,000. "
            "Model 3/Y accounted for 432,000 units. Cybertruck deliveries reached 16,000 units. "
            "Energy storage deployment hit a record 7.4 GWh. "
            "The stock rose 8% in after-hours trading following the announcement."
        ),
    },
    {
        "source": "Bloomberg — Global Semiconductor Outlook 2025",
        "content": (
            "Global semiconductor sales are projected to reach $680 billion in 2025, up 13% from 2024. "
            "AI chip demand continues to drive growth, with NVIDIA maintaining 80%+ market share in data center GPUs. "
            "TSMC's advanced packaging capacity remains constrained through H1 2026. "
            "Memory chip prices (DRAM, NAND) are stabilizing after a prolonged downturn."
        ),
    },
    {
        "source": "SEC Filing — Microsoft 10-K FY2025",
        "content": (
            "Microsoft reported total revenue of $261 billion for FY2025, up 16% YoY. "
            "Azure cloud revenue grew 29% YoY. AI services contributed approximately 8% of Azure growth. "
            "Operating income was $115 billion with a 44% operating margin. "
            "The company invested $55 billion in capital expenditures, primarily for AI infrastructure. "
            "Microsoft 365 Commercial seat growth was 11%."
        ),
    },
    {
        "source": "Reuters — China Stimulus Package November 2025",
        "content": (
            "China announced a ¥2 trillion ($275 billion) fiscal stimulus package focused on infrastructure, "
            "real estate stabilization, and consumer subsidies. The PBOC cut the reserve requirement ratio (RRR) "
            "by 50 basis points, releasing approximately ¥1 trillion in long-term liquidity. "
            "The CSI 300 index rallied 3.2% on the announcement. "
            "Analysts expect the measures to boost GDP by 0.5-0.8 percentage points in 2026."
        ),
    },
    {
        "source": "JPMorgan Global Markets Strategy — December 2025",
        "content": (
            "JPMorgan recommends overweight allocation to US large-cap equities, Japanese equities, "
            "and investment-grade credit. The S&P 500 year-end 2026 target is 6,500. "
            "Key risks include: escalation of trade tensions, persistent services inflation, "
            "and geopolitical instability in the Middle East. "
            "Recommended sectors: Technology, Healthcare, Financials. Underweight: Utilities, Consumer Staples."
        ),
    },
    {
        "source": "CoinDesk — Bitcoin ETF Flows Report November 2025",
        "content": (
            "US spot Bitcoin ETFs recorded $2.4 billion in net inflows during November 2025, "
            "the highest monthly total since March 2024. BlackRock's IBIT led with $1.2 billion. "
            "Total AUM across all spot Bitcoin ETFs reached $95 billion. "
            "Ethereum spot ETFs saw $800 million in inflows. Institutions now represent 65% of ETF holders."
        ),
    },
]


def _compute_relevance(query: str, doc: dict) -> float:
    """Simple TF-IDF-like relevance scoring for demo."""
    query_terms = set(re.findall(r'\b\w{4,}\b', query.lower()))
    if not query_terms:
        return 0.5

    content_lower = doc["content"].lower()
    title_lower = doc["source"].lower()

    content_hits = sum(1 for t in query_terms if t in content_lower)
    title_hits = sum(1 for t in query_terms if t in title_lower)

    # Title matches weighted higher
    score = (content_hits * 0.15 + title_hits * 0.35)
    return min(round(score, 2), 0.99)


def _extract_snippet(content: str, query: str, max_len: int = 250) -> str:
    """Extract a relevant snippet from the document."""
    query_terms = [t for t in re.findall(r'\b\w{4,}\b', query.lower())]
    sentences = re.split(r'(?<=[.!?])\s+', content)

    best_sentence = ""
    best_score = 0
    for s in sentences:
        score = sum(1 for t in query_terms if t in s.lower())
        if score > best_score:
            best_score = score
            best_sentence = s

    if best_sentence and len(best_sentence) > 20:
        return best_sentence[:max_len]
    return content[:max_len]


def _generate_answer(question: str, documents: list[dict]) -> str:
    """Generate a demo answer based on retrieved documents."""
    if not documents:
        return (
            "Based on the available financial knowledge base, I don't have enough "
            "specific information to answer this question confidently. In production, "
            "Fin-train RAG would search across Reuters, Bloomberg, SEC filings, and "
            "other financial sources to find relevant information."
        )

    # Combine relevant snippets
    snippets = [d["snippet"] for d in documents]
    combined = " ".join(snippets)

    # Generate a simple response based on the retrieved context
    question_lower = question.lower()

    if "revenue" in question_lower or "earnings" in question_lower:
        return (
            f"Based on the retrieved financial documents, here is the revenue/earnings analysis:\n\n"
            f"{documents[0]['snippet']}\n\n"
            f"Source: {documents[0]['source']}.\n\n"
            f"In summary, the data shows strong financial performance with revenue growth "
            f"driven by core product segments and services. "
            f"[Note: This is a demo response. Real Fin-train RAG uses instruct-Fin-train "
            f"fine-tuned on financial instruction data.]"
        )

    if "rate" in question_lower or "fed" in question_lower or "inflation" in question_lower:
        return (
            f"Regarding monetary policy and rates:\n\n"
            f"{documents[0]['snippet']}\n\n"
            f"Source: {documents[0]['source']}.\n\n"
            f"The current stance suggests a cautious approach with data-dependent decisions ahead."
        )

    # General answer
    return (
        f"Based on the retrieved financial context:\n\n"
        f"{documents[0]['snippet']}\n\n"
        f"Source: {documents[0]['source']}.\n\n"
        f"This information addresses your query about '{question}'. "
        f"For deeper analysis, Fin-train RAG would retrieve additional documents and use "
        f"the instruction-tuned model for a comprehensive response."
    )


def retrieve_and_answer(question: str, top_k: int = 3) -> dict:
    """Simulate RAG pipeline: retrieve documents and generate answer."""

    # Compute relevance scores
    scored = []
    for doc in _KNOWLEDGE_BASE:
        score = _compute_relevance(question, doc)
        if score > 0:
            scored.append((score, doc))

    # Sort by relevance and take top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    top_docs = scored[:top_k]

    # Build retrieved document list
    retrieved = []
    for score, doc in top_docs:
        retrieved.append({
            "source": doc["source"],
            "snippet": _extract_snippet(doc["content"], question),
            "relevance_score": score,
        })

    # Generate answer
    answer = _generate_answer(question, retrieved)

    return {
        "question": question,
        "answer": answer,
        "retrieved_documents": retrieved,
    }

"""Fin-train Forecaster — stock prediction with real data + simulated LLM analysis."""

import random
from datetime import datetime, timedelta
from typing import Optional


def _fetch_stock_data(symbol: str, n_weeks: int):
    """Fetch real stock data from yfinance. Returns (info_dict, price_history_list, None or error)."""
    try:
        import yfinance as yf
    except ImportError:
        return None, None, "yfinance not installed. Run: pip install yfinance"

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            return None, None, f"No data found for symbol '{symbol}'. Check the ticker."

        # Get price history
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=n_weeks + 1)
        hist = ticker.history(start=start_date.strftime("%Y-%m-%d"),
                              end=end_date.strftime("%Y-%m-%d"))

        if hist.empty:
            return None, None, f"No price history found for '{symbol}'."

        price_history = []
        for idx, row in hist.iterrows():
            price_history.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open_price": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return info, price_history, None
    except Exception as e:
        return None, None, f"Error fetching data: {str(e)}"


def _generate_simulated_analysis(symbol: str, company_name: str, price_history: list, info: dict) -> dict:
    """Generate a Fin-train-style structured analysis (simulated LLM output)."""

    if not price_history:
        return _generate_fallback_analysis(symbol, company_name)

    # Calculate actual price movements
    current_price = price_history[-1]["close"]
    start_price = price_history[0]["close"]
    change_pct = ((current_price - start_price) / start_price) * 100 if start_price else 0

    # Recent trend (last 3 days)
    recent_prices = [p["close"] for p in price_history[-3:]] if len(price_history) >= 3 else [p["close"] for p in price_history]
    recent_trend = "upward" if recent_prices[-1] > recent_prices[0] else "downward"

    # Volume trend
    avg_volume = sum(p["volume"] for p in price_history) / len(price_history)
    recent_volume = price_history[-1]["volume"] if price_history else 0
    volume_signal = "above average" if recent_volume > avg_volume * 1.2 else "below average"

    # Generate analysis based on actual data patterns
    if change_pct > 3:
        positive_factors = [
            f"{symbol} has shown strong momentum with a {change_pct:.1f}% gain over the period.",
            f"Trading volume is {volume_signal}, indicating {'strong' if volume_signal == 'above average' else 'moderate'} market participation.",
            f"The recent {recent_trend} trend suggests sustained buying pressure.",
        ]
        concerns = [
            "After a significant rally, short-term profit-taking may occur.",
            "Technical indicators may signal overbought conditions.",
            "Macroeconomic factors (interest rates, inflation) could shift sentiment.",
        ]
        prediction = f"↑ Moderately Bullish — expected {random.uniform(0.5, 3.0):.1f}% upside next week"
        analysis = (
            f"{company_name} has demonstrated strong price performance with a {change_pct:.1f}% gain. "
            f"Volume is {volume_signal} and the {recent_trend} near-term trend supports continued momentum. "
            "However, the rapid appreciation raises the risk of a short-term pullback. "
            "Investors should monitor upcoming earnings and macro developments."
        )
    elif change_pct < -3:
        positive_factors = [
            f"The {abs(change_pct):.1f}% decline may present a buying opportunity at lower valuations.",
            f"Volume is {volume_signal}, suggesting {'capitulation selling may be near exhaustion' if volume_signal == 'above average' else 'controlled selling pressure'}.",
            "Long-term fundamentals may remain intact despite short-term headwinds.",
        ]
        concerns = [
            f"{symbol} has declined {abs(change_pct):.1f}%, indicating significant selling pressure.",
            f"The recent {recent_trend} trend suggests continued bearish sentiment.",
            "Negative sector rotation or company-specific issues may persist.",
        ]
        prediction = f"↓ Cautiously Bearish — potential {random.uniform(0.5, 3.0):.1f}% further downside"
        analysis = (
            f"{company_name} has experienced a notable {abs(change_pct):.1f}% decline. "
            f"Volume is {volume_signal}, and the {recent_trend} trend indicates ongoing pressure. "
            "While lower prices may attract value buyers, the current momentum suggests caution. "
            "Key support levels and upcoming catalysts should be watched closely."
        )
    else:
        positive_factors = [
            f"{symbol} is trading in a stable range with {change_pct:+.1f}% change.",
            "Consolidation at current levels may build a base for the next move.",
            f"Volume at {volume_signal} levels indicates orderly market conditions.",
        ]
        concerns = [
            "Lack of clear directional catalyst keeps the stock range-bound.",
            "Low conviction among market participants may delay a breakout.",
            "External macro events could trigger unexpected volatility.",
        ]
        direction = "up" if change_pct > 0 else "down"
        prediction = f"↔ Neutral-to-Slightly {'Bullish' if direction == 'up' else 'Bearish'} — ~{abs(change_pct):.1f}% move expected"
        analysis = (
            f"{company_name} has been relatively stable with a {change_pct:+.1f}% net change. "
            f"The {recent_trend} recent bias and {volume_signal} volume suggest a balanced market. "
            "A breakout above resistance or breakdown below support will likely determine the next trend. "
            "Watch for earnings, guidance updates, or sector catalysts."
        )

    return {
        "positive_developments": positive_factors,
        "potential_concerns": concerns,
        "prediction": prediction,
        "analysis": analysis,
    }


def _generate_fallback_analysis(symbol: str, company_name: str) -> dict:
    """Fallback analysis when no real data is available."""
    return {
        "positive_developments": [
            f"{company_name} continues to execute on its strategic initiatives.",
            "Industry tailwinds support long-term growth.",
        ],
        "potential_concerns": [
            "Macroeconomic uncertainty may impact near-term performance.",
            "Competitive pressures in the sector are intensifying.",
        ],
        "prediction": "↔ Neutral — insufficient data for directional prediction",
        "analysis": (
            f"Without sufficient real-time data for {company_name}, a definitive prediction "
            "cannot be made. In production, Fin-train Forecaster would use real-time yfinance data, "
            "Finnhub news, and optional Adanos market sentiment signals to generate a detailed analysis."
        ),
    }


def generate_forecast(symbol: str, n_weeks: int = 2,
                      include_sentiment: bool = True,
                      include_financials: bool = True) -> dict:
    """Generate a stock forecast report using real price data + simulated LLM analysis."""

    info, price_history, error = _fetch_stock_data(symbol, n_weeks)

    if error:
        return {
            "symbol": symbol,
            "company_name": symbol,
            "current_price": 0.0,
            "period": {"start_date": "", "end_date": "", "n_weeks": n_weeks},
            "price_history": [],
            "positive_developments": [],
            "potential_concerns": [],
            "prediction": "N/A",
            "analysis": error,
            "error": error,
        }

    company_name = info.get("longName") or info.get("shortName") or symbol
    current_price = info.get("regularMarketPrice") or info.get("currentPrice") or (
        price_history[-1]["close"] if price_history else 0.0
    )
    market_cap = info.get("marketCap")
    market_cap_str = f"${market_cap:,.0f}" if market_cap else "N/A"
    sector = info.get("sector", "Unknown")

    start_date = price_history[0]["date"] if price_history else ""
    end_date = price_history[-1]["date"] if price_history else ""

    # Generate analysis
    analysis = _generate_simulated_analysis(symbol, company_name, price_history, info)

    return {
        "symbol": symbol,
        "company_name": company_name,
        "current_price": round(current_price, 2),
        "market_cap": market_cap_str,
        "sector": sector,
        "period": {"start_date": start_date, "end_date": end_date, "n_weeks": n_weeks},
        "price_history": price_history[-10:],  # Return last 10 data points
        "positive_developments": analysis["positive_developments"],
        "potential_concerns": analysis["potential_concerns"],
        "prediction": analysis["prediction"],
        "analysis": analysis["analysis"],
        "data_sources": {
            "price_data": "yfinance (real-time)",
            "market_sentiment": "simulated" if include_sentiment else "disabled",
            "financials": "yfinance" if include_financials else "disabled",
            "llm_analysis": "Fin-train Forecaster LoRA [DEMO — simulated]",
        },
    }

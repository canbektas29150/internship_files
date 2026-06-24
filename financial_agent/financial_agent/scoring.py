from __future__ import annotations

from typing import Any, Dict, List
from schemas import MetricScore, ScoreCard


def clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


def score_revenue_growth(value):
    if value is None:
        return 50
    # yfinance revenueGrowth often decimal, e.g. 0.06
    return clamp(50 + float(value) * 250)


def score_margin(value):
    if value is None:
        return 50
    return clamp(40 + float(value) * 200)


def score_fcf(value):
    if value is None:
        return 50
    if value > 0:
        return 70 if value < 5_000_000_000 else 85
    return 30


def score_pe(value):
    if value is None:
        return 50
    value = float(value)
    if value <= 0:
        return 35
    if 10 <= value <= 25:
        return 75
    if 25 < value <= 40:
        return 55
    if value < 10:
        return 60
    return 35


def score_debt_risk(value):
    if value is None:
        return 50
    value = float(value)
    if value < 50:
        return 25
    if value < 120:
        return 45
    if value < 250:
        return 65
    return 85


def build_investment_score(snapshot: Dict[str, Any], sources_count: int) -> ScoreCard:
    info = snapshot.get("info", {})
    metrics: List[MetricScore] = [
        MetricScore(
            name="Revenue Growth",
            value=str(info.get("revenueGrowth", "Not available")),
            score=score_revenue_growth(info.get("revenueGrowth")),
            weight=0.22,
            source=snapshot.get("data_source", "yfinance"),
            explanation="Revenue growth shows whether the core business is expanding.",
        ),
        MetricScore(
            name="Profit Margin",
            value=str(info.get("profitMargins", "Not available")),
            score=score_margin(info.get("profitMargins")),
            weight=0.18,
            source=snapshot.get("data_source", "yfinance"),
            explanation="Profit margin indicates earnings quality and pricing power.",
        ),
        MetricScore(
            name="Free Cash Flow",
            value=str(info.get("freeCashflow", "Not available")),
            score=score_fcf(info.get("freeCashflow")),
            weight=0.20,
            source=snapshot.get("data_source", "yfinance"),
            explanation="Free cash flow supports investment, dividends, buybacks and debt reduction.",
        ),
        MetricScore(
            name="Valuation / P/E",
            value=str(info.get("trailingPE", "Not available")),
            score=score_pe(info.get("trailingPE")),
            weight=0.16,
            source=snapshot.get("data_source", "yfinance"),
            explanation="P/E is used as a simple valuation sanity check.",
        ),
        MetricScore(
            name="Research Coverage / Sources",
            value=f"{sources_count} source items",
            score=clamp(40 + sources_count * 5),
            weight=0.12,
            source="DDGS/web search",
            explanation="More relevant sources improve confidence in the analysis.",
        ),
        MetricScore(
            name="Strategic Momentum",
            value="Inferred from prompt + news plan",
            score=65,
            weight=0.12,
            source="Research planner",
            explanation="Strategic momentum is estimated from the type of catalysts found/asked.",
        ),
    ]
    total = round(sum(m.score * m.weight for m in metrics), 1)
    return ScoreCard(label="Investment Score", total_score=total, metrics=metrics)


def build_risk_score(snapshot: Dict[str, Any], sources_count: int, sec_status: str) -> ScoreCard:
    info = snapshot.get("info", {})
    beta = info.get("beta")
    if beta is None:
        beta_score = 50
    else:
        beta_score = clamp(35 + float(beta) * 25)

    sec_score = 25 if sec_status == "ok" else 55
    missing_data_score = 35 if snapshot.get("status") == "ok" else 70

    metrics: List[MetricScore] = [
        MetricScore(
            name="Leverage Risk",
            value=str(info.get("debtToEquity", "Not available")),
            score=score_debt_risk(info.get("debtToEquity")),
            weight=0.22,
            source=snapshot.get("data_source", "yfinance"),
            explanation="Higher debt/equity generally increases balance-sheet risk.",
        ),
        MetricScore(
            name="Market Volatility / Beta",
            value=str(info.get("beta", "Not available")),
            score=beta_score,
            weight=0.18,
            source=snapshot.get("data_source", "yfinance"),
            explanation="Beta approximates sensitivity to market movements.",
        ),
        MetricScore(
            name="Data Availability Risk",
            value=snapshot.get("status", "unknown"),
            score=missing_data_score,
            weight=0.18,
            source="Tool status",
            explanation="Missing live data increases uncertainty.",
        ),
        MetricScore(
            name="SEC / Filing Transparency Risk",
            value=sec_status,
            score=sec_score,
            weight=0.16,
            source="SEC lookup",
            explanation="SEC availability reduces reporting uncertainty for US-listed companies.",
        ),
        MetricScore(
            name="News/Event Risk",
            value=f"{sources_count} source items checked",
            score=45 if sources_count >= 5 else 60,
            weight=0.16,
            source="DDGS/web search",
            explanation="Limited source count increases event-risk uncertainty.",
        ),
        MetricScore(
            name="Macro / Sector Risk",
            value=str(info.get("sector", "Unknown")),
            score=50,
            weight=0.10,
            source="Sector inference",
            explanation="Default neutral macro risk until explicit macro data is added.",
        ),
    ]
    # Compute total risk score out of 100, then scale to a 1–10 range.
    total_raw = sum(m.score * m.weight for m in metrics)
    total = round(total_raw / 10, 1)
    return ScoreCard(label="Risk Score", total_score=total, metrics=metrics)

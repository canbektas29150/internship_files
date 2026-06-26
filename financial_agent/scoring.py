from __future__ import annotations

from typing import Any, Dict, List

from schemas import MetricScore, ScoreCard, SourceItem
from tools import estimate_source_quality


def clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


def score_revenue_growth(value):
    if value is None:
        return 50
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
    # yfinance debtToEquity often uses percentage-like values.
    if value < 50:
        return 25
    if value < 120:
        return 45
    if value < 250:
        return 65
    return 85


def _evidence(source: str, field: str, raw_value: Any, source_url: str = "", note: str = "") -> List[Dict[str, Any]]:
    return [{
        "source": source,
        "field": field,
        "raw_value": raw_value,
        "source_url": source_url,
        "note": note,
    }]


def _metric_validation(value: Any, source_status: str) -> Dict[str, Any]:
    return {
        "value_available": value is not None,
        "source_status": source_status,
        "warning": "missing_value_neutral_score_used" if value is None else "",
    }


def build_investment_score(snapshot: Dict[str, Any], sources_count: int) -> ScoreCard:
    info = snapshot.get("info", {})
    source = snapshot.get("data_source", "yfinance")
    source_url = snapshot.get("source_url", "")
    status = snapshot.get("status", "unknown")

    metrics: List[MetricScore] = [
        MetricScore(
            name="Revenue Growth",
            value=str(info.get("revenueGrowth", "Not available")),
            score=score_revenue_growth(info.get("revenueGrowth")),
            weight=0.22,
            source=source,
            explanation="Revenue growth shows whether the core business is expanding.",
            evidence=_evidence(source, "revenueGrowth", info.get("revenueGrowth"), source_url),
            source_url=source_url,
            validation=_metric_validation(info.get("revenueGrowth"), status),
        ),
        MetricScore(
            name="Profit Margin",
            value=str(info.get("profitMargins", "Not available")),
            score=score_margin(info.get("profitMargins")),
            weight=0.18,
            source=source,
            explanation="Profit margin indicates earnings quality and pricing power.",
            evidence=_evidence(source, "profitMargins", info.get("profitMargins"), source_url),
            source_url=source_url,
            validation=_metric_validation(info.get("profitMargins"), status),
        ),
        MetricScore(
            name="Free Cash Flow",
            value=str(info.get("freeCashflow", "Not available")),
            score=score_fcf(info.get("freeCashflow")),
            weight=0.20,
            source=source,
            explanation="Free cash flow supports investment, dividends, buybacks and debt reduction.",
            evidence=_evidence(source, "freeCashflow", info.get("freeCashflow"), source_url),
            source_url=source_url,
            validation=_metric_validation(info.get("freeCashflow"), status),
        ),
        MetricScore(
            name="Valuation / P/E",
            value=str(info.get("trailingPE", "Not available")),
            score=score_pe(info.get("trailingPE")),
            weight=0.16,
            source=source,
            explanation="P/E is used as a simple valuation sanity check.",
            evidence=_evidence(source, "trailingPE", info.get("trailingPE"), source_url),
            source_url=source_url,
            validation=_metric_validation(info.get("trailingPE"), status),
        ),
        MetricScore(
            name="Research Coverage / Sources",
            value=f"{sources_count} source items",
            score=clamp(40 + sources_count * 5),
            weight=0.12,
            source="DDGS/web search",
            explanation="More relevant sources improve confidence in the analysis.",
            evidence=_evidence("DDGS/web search", "sources_count", sources_count, "https://duckduckgo.com"),
            source_url="https://duckduckgo.com",
            validation={"value_available": sources_count > 0, "warning": "low_source_count" if sources_count < 5 else ""},
        ),
        MetricScore(
            name="Strategic Momentum",
            value="Inferred from prompt + news plan",
            score=65,
            weight=0.12,
            source="Research planner",
            explanation="Strategic momentum is estimated from the type of catalysts found/asked.",
            evidence=_evidence("Research planner", "intent_and_queries", "inferred", ""),
            validation={"value_available": True, "warning": "qualitative_proxy_metric"},
        ),
    ]
    total = round(sum(m.score * m.weight for m in metrics), 1)
    confidence = compute_score_confidence(metrics, snapshot_status=status, sources_count=sources_count)
    return ScoreCard(
        label="Investment Score",
        total_score=total,
        metrics=metrics,
        evidence_map=build_evidence_map(metrics),
        confidence=confidence,
    )


def build_risk_score(snapshot: Dict[str, Any], sources_count: int, sec_status: str) -> ScoreCard:
    info = snapshot.get("info", {})
    source = snapshot.get("data_source", "yfinance")
    source_url = snapshot.get("source_url", "")
    status = snapshot.get("status", "unknown")
    beta = info.get("beta")
    beta_score = 50 if beta is None else clamp(35 + float(beta) * 25)
    sec_score = 25 if sec_status == "ok" else 55
    missing_data_score = 35 if snapshot.get("status") == "ok" else 70

    metrics: List[MetricScore] = [
        MetricScore(
            name="Leverage Risk",
            value=str(info.get("debtToEquity", "Not available")),
            score=score_debt_risk(info.get("debtToEquity")),
            weight=0.22,
            source=source,
            explanation="Higher debt/equity generally increases balance-sheet risk.",
            evidence=_evidence(source, "debtToEquity", info.get("debtToEquity"), source_url),
            source_url=source_url,
            validation=_metric_validation(info.get("debtToEquity"), status),
        ),
        MetricScore(
            name="Market Volatility / Beta",
            value=str(info.get("beta", "Not available")),
            score=beta_score,
            weight=0.18,
            source=source,
            explanation="Beta approximates sensitivity to market movements.",
            evidence=_evidence(source, "beta", info.get("beta"), source_url),
            source_url=source_url,
            validation=_metric_validation(info.get("beta"), status),
        ),
        MetricScore(
            name="Data Availability Risk",
            value=snapshot.get("status", "unknown"),
            score=missing_data_score,
            weight=0.18,
            source="Tool status",
            explanation="Missing live data increases uncertainty.",
            evidence=_evidence("Tool status", "financial_snapshot.status", snapshot.get("status"), source_url),
            source_url=source_url,
            validation={"value_available": snapshot.get("status") == "ok", "warning": "financial_data_not_ok" if snapshot.get("status") != "ok" else ""},
        ),
        MetricScore(
            name="SEC / Filing Transparency Risk",
            value=sec_status,
            score=sec_score,
            weight=0.16,
            source="SEC lookup",
            explanation="SEC availability reduces reporting uncertainty for US-listed companies.",
            evidence=_evidence("SEC lookup", "sec_status", sec_status, "https://www.sec.gov/files/company_tickers.json"),
            source_url="https://www.sec.gov/files/company_tickers.json",
            validation={"value_available": sec_status == "ok", "warning": "sec_lookup_not_ok" if sec_status != "ok" else ""},
        ),
        MetricScore(
            name="News/Event Risk",
            value=f"{sources_count} source items checked",
            score=45 if sources_count >= 5 else 60,
            weight=0.16,
            source="DDGS/web search",
            explanation="Limited source count increases event-risk uncertainty.",
            evidence=_evidence("DDGS/web search", "sources_count", sources_count, "https://duckduckgo.com"),
            source_url="https://duckduckgo.com",
            validation={"value_available": sources_count > 0, "warning": "low_source_count" if sources_count < 5 else ""},
        ),
        MetricScore(
            name="Macro / Sector Risk",
            value=str(info.get("sector", "Unknown")),
            score=50,
            weight=0.10,
            source="Sector inference",
            explanation="Default neutral macro risk until explicit macro data is added.",
            evidence=_evidence(source, "sector", info.get("sector"), source_url, "neutral macro proxy"),
            source_url=source_url,
            validation={"value_available": info.get("sector") is not None, "warning": "neutral_proxy_metric"},
        ),
    ]
    total_100 = sum(m.score * m.weight for m in metrics)
    total_10 = round(total_100 / 10, 1)
    confidence = compute_score_confidence(metrics, snapshot_status=status, sources_count=sources_count, sec_status=sec_status)
    return ScoreCard(
        label="Risk Score",
        total_score=total_10,
        metrics=metrics,
        evidence_map=build_evidence_map(metrics),
        confidence=confidence,
    )


def compute_score_confidence(metrics: List[MetricScore], snapshot_status: str, sources_count: int, sec_status: str = "") -> float:
    available = sum(1 for m in metrics if m.validation.get("value_available"))
    base = available / max(1, len(metrics))
    if snapshot_status == "ok":
        base += 0.15
    if sources_count >= 5:
        base += 0.10
    elif sources_count == 0:
        base -= 0.15
    if sec_status == "ok":
        base += 0.05
    return round(clamp(base, 0.05, 0.98), 3)


def build_evidence_map(metrics: List[MetricScore]) -> Dict[str, Any]:
    rows = []
    for m in metrics:
        rows.append({
            "metric": m.name,
            "score": m.score,
            "weight": m.weight,
            "weighted_contribution": round(m.score * m.weight, 2),
            "source": m.source,
            "source_url": m.source_url,
            "evidence": m.evidence,
            "validation": m.validation,
        })
    return {"metrics": rows, "notes": "Each score is mapped back to one or more raw fields/sources."}


def build_global_evidence_map(
    investment: ScoreCard,
    risk: ScoreCard,
    financial_snapshot: Dict[str, Any],
    sec_snapshot: Dict[str, Any],
    sources: List[SourceItem],
) -> Dict[str, Any]:
    quality = [estimate_source_quality(s) for s in sources]
    return {
        "investment_score": investment.evidence_map,
        "risk_score": risk.evidence_map,
        "financial_data": {
            "source": financial_snapshot.get("data_source"),
            "source_url": financial_snapshot.get("source_url"),
            "status": financial_snapshot.get("status"),
            "returned_fields": financial_snapshot.get("returned_fields", []),
            "missing_fields": financial_snapshot.get("missing_fields", []),
            "validation": financial_snapshot.get("validation", {}),
        },
        "sec_data": {
            "source": "SEC company_tickers.json",
            "source_url": sec_snapshot.get("source_url", "https://www.sec.gov/files/company_tickers.json"),
            "status": sec_snapshot.get("status"),
            "cik": sec_snapshot.get("cik"),
            "validation": sec_snapshot.get("validation", {}),
        },
        "source_quality": quality,
    }

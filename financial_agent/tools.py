from __future__ import annotations

import os
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Tuple

import requests

from schemas import ResearchQuery, SourceItem


FINANCIAL_FIELDS = [
    "longName", "sector", "industry", "marketCap", "currentPrice",
    "trailingPE", "forwardPE", "pegRatio", "priceToBook",
    "revenueGrowth", "grossMargins", "operatingMargins", "profitMargins",
    "freeCashflow", "totalDebt", "debtToEquity", "beta",
    "dividendYield", "recommendationMean", "targetMeanPrice",
]

SOURCE_QUALITY_RULES = {
    "sec.gov": 100,
    "investor.apple.com": 98,
    "ibm.com": 96,
    "microsoft.com": 96,
    "nvidia.com": 96,
    "investorrelations": 92,
    "reuters.com": 95,
    "apnews.com": 92,
    "bloomberg.com": 92,
    "cnbc.com": 86,
    "marketwatch.com": 82,
    "yahoo.com": 80,
    "finance.yahoo.com": 88,
    "seekingalpha.com": 72,
    "fool.com": 70,
    "reddit.com": 45,
    "twitter.com": 40,
    "x.com": 40,
}


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host.replace("www.", "")
    except Exception:
        return ""


def estimate_source_quality(source: SourceItem) -> Dict[str, Any]:
    domain = _domain(source.url)
    score = 65
    reason = "Generic web result; quality depends on source reputation."
    if source.source_type == "system":
        return {"title": source.title, "url": source.url, "domain": domain, "score": 0, "reason": "Tool/search failed; not a usable external source."}
    for key, val in SOURCE_QUALITY_RULES.items():
        if key in domain or key in source.url.lower():
            score = val
            if val >= 95:
                reason = "Highly reliable primary/major financial source."
            elif val >= 85:
                reason = "Recognized financial/news source."
            elif val >= 70:
                reason = "Useful secondary market commentary; verify before relying on it."
            else:
                reason = "Low-confidence/community/social source."
            break
    if not source.url:
        score = 0
        reason = "No URL returned."
    return {"title": source.title, "url": source.url, "domain": domain, "score": score, "reason": reason}


def source_quality_report(sources: List[SourceItem]) -> List[Dict[str, Any]]:
    return [estimate_source_quality(s) for s in sources]


def validate_financial_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    info = snapshot.get("info", {}) or {}
    returned = list(info.keys())
    missing = [f for f in FINANCIAL_FIELDS if f not in returned or info.get(f) is None]
    critical = ["marketCap", "currentPrice", "trailingPE", "revenueGrowth", "profitMargins", "freeCashflow", "debtToEquity", "beta"]
    critical_missing = [f for f in critical if f not in returned or info.get(f) is None]
    status_ok = snapshot.get("status") == "ok"
    confidence = max(0.15, min(0.98, (len(returned) / max(1, len(FINANCIAL_FIELDS))) * 1.05)) if status_ok else 0.25
    return {
        "status_ok": status_ok,
        "returned_fields_count": len(returned),
        "missing_fields_count": len(missing),
        "critical_missing": critical_missing,
        "has_market_data": bool(info.get("marketCap") or info.get("currentPrice")),
        "has_profitability": any(info.get(k) is not None for k in ["profitMargins", "grossMargins", "operatingMargins"]),
        "has_risk_metrics": any(info.get(k) is not None for k in ["debtToEquity", "beta", "totalDebt"]),
        "confidence": round(confidence, 3),
    }


def get_financial_snapshot(ticker: str) -> Dict[str, Any]:
    """Fetch a financial snapshot with yfinance and return validation metadata."""
    snapshot: Dict[str, Any] = {
        "ticker": ticker,
        "data_source": "yfinance",
        "source_url": f"https://finance.yahoo.com/quote/{ticker}",
        "status": "not_loaded",
        "error": None,
        "requested_fields": FINANCIAL_FIELDS,
        "returned_fields": [],
        "missing_fields": FINANCIAL_FIELDS[:],
        "info": {},
        "validation": {},
        "confidence": 0.0,
    }

    try:
        import yfinance as yf
        obj = yf.Ticker(ticker)
        info = obj.info or {}
        snapshot["info"] = {k: info.get(k) for k in FINANCIAL_FIELDS if k in info and info.get(k) is not None}
        snapshot["returned_fields"] = list(snapshot["info"].keys())
        snapshot["missing_fields"] = [k for k in FINANCIAL_FIELDS if k not in snapshot["returned_fields"]]
        snapshot["status"] = "ok" if snapshot["info"] else "empty"
        snapshot["validation"] = validate_financial_snapshot(snapshot)
        snapshot["confidence"] = snapshot["validation"].get("confidence", 0.0)
        return snapshot
    except Exception as exc:
        snapshot["status"] = "error"
        snapshot["error"] = str(exc)
        snapshot["validation"] = validate_financial_snapshot(snapshot)
        snapshot["confidence"] = 0.1
        return snapshot


def _get_ddgs_class():
    try:
        from ddgs import DDGS  # type: ignore
        return DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS  # type: ignore
            return DDGS
        except Exception:
            return None


def web_search(query: str, max_results: int = 5, topic: str = "web") -> Tuple[List[SourceItem], Dict[str, Any]]:
    """Run a DDGS/DuckDuckGo search and return sources plus trace metadata."""
    results: List[SourceItem] = []
    meta: Dict[str, Any] = {
        "query": query,
        "topic": topic,
        "tool": "DDGS.text",
        "requested_results": max_results,
        "returned_results": 0,
        "used_results": 0,
        "discarded_results": 0,
        "discard_reasons": [],
        "status": "not_loaded",
        "error": None,
    }
    DDGS = _get_ddgs_class()
    if DDGS is None:
        meta["status"] = "error"
        meta["error"] = "ddgs / duckduckgo_search package is not installed."
        return [SourceItem("Web search unavailable", "", meta["error"], "system")], meta

    try:
        with DDGS() as ddgs:
            raw_items = list(ddgs.text(query, max_results=max_results))
        meta["returned_results"] = len(raw_items)
        seen_urls = set()
        for item in raw_items:
            title = item.get("title") or "Untitled"
            url = item.get("href") or item.get("url") or ""
            snippet = item.get("body") or item.get("snippet") or ""
            if not url:
                meta["discarded_results"] += 1
                meta["discard_reasons"].append("missing_url")
                continue
            if url in seen_urls:
                meta["discarded_results"] += 1
                meta["discard_reasons"].append("duplicate_url")
                continue
            seen_urls.add(url)
            results.append(SourceItem(title=title, url=url, snippet=snippet, source_type=f"web:{topic}"))
        meta["used_results"] = len(results)
        meta["status"] = "ok"
        return results, meta
    except Exception as exc:
        meta["status"] = "error"
        meta["error"] = str(exc)
        return [SourceItem("Web search unavailable", "", f"DDGS search failed or internet unavailable: {exc}", "system")], meta


def run_research_queries_with_trace(queries: List[ResearchQuery], max_results_per_query: int = 4) -> Tuple[List[SourceItem], Dict[str, Any]]:
    all_sources: List[SourceItem] = []
    query_logs: List[Dict[str, Any]] = []
    seen = set()
    global_discards = 0
    global_reasons: List[str] = []
    for q in queries:
        query_sources, meta = web_search(q.query, max_results=max_results_per_query, topic=q.topic)
        used_for_query = 0
        for source in query_sources:
            key = source.url or f"{source.title}-{source.snippet[:30]}"
            if key in seen:
                global_discards += 1
                global_reasons.append("duplicate_across_queries")
                continue
            seen.add(key)
            all_sources.append(source)
            used_for_query += 1
        meta["used_after_dedupe"] = used_for_query
        query_logs.append(meta)
    quality = source_quality_report(all_sources)
    trace = {
        "queries_count": len(queries),
        "query_logs": query_logs,
        "total_sources_used": len(all_sources),
        "total_discarded_across_queries": global_discards,
        "discard_reasons_across_queries": sorted(set(global_reasons)),
        "source_quality": quality,
        "avg_source_quality": round(sum(q["score"] for q in quality) / max(1, len(quality)), 1) if quality else 0,
    }
    return all_sources, trace


def run_research_queries(queries, max_results_per_query: int = 4) -> List[SourceItem]:
    sources, _ = run_research_queries_with_trace(queries, max_results_per_query=max_results_per_query)
    return sources


def sec_company_lookup(ticker: str) -> Dict[str, Any]:
    """SEC company_tickers endpointinden basit CIK lookup yapar."""
    headers = {
        "User-Agent": os.getenv("SEC_USER_AGENT", "financial-agent-student-project contact@example.com"),
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    }
    output = {
        "ticker": ticker,
        "cik": None,
        "status": "not_loaded",
        "error": None,
        "source_url": "https://www.sec.gov/files/company_tickers.json",
        "validation": {},
        "confidence": 0.0,
    }
    try:
        url = output["source_url"]
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for _, row in data.items():
            if row.get("ticker", "").upper() == ticker.upper():
                output["cik"] = str(row.get("cik_str")).zfill(10)
                output["status"] = "ok"
                output["validation"] = {"ticker_matched": True, "has_cik": True, "records_checked": len(data)}
                output["confidence"] = 0.96
                return output
        output["status"] = "not_found"
        output["validation"] = {"ticker_matched": False, "has_cik": False, "records_checked": len(data)}
        output["confidence"] = 0.45
        return output
    except Exception as exc:
        output["status"] = "error"
        output["error"] = str(exc)
        output["validation"] = {"ticker_matched": False, "has_cik": False, "error": str(exc)}
        output["confidence"] = 0.2
        return output

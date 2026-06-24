from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
import requests
from schemas import SourceItem


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def get_financial_snapshot(ticker: str) -> Dict[str, Any]:
    """yfinance ile finansal snapshot çeker. Hata olursa uygulama çökmez."""
    snapshot: Dict[str, Any] = {
        "ticker": ticker,
        "data_source": "yfinance",
        "status": "not_loaded",
        "error": None,
        "info": {},
    }

    try:
        import yfinance as yf
        obj = yf.Ticker(ticker)
        info = obj.info or {}
        wanted_keys = [
            "longName", "sector", "industry", "marketCap", "currentPrice",
            "trailingPE", "forwardPE", "pegRatio", "priceToBook",
            "revenueGrowth", "grossMargins", "operatingMargins", "profitMargins",
            "freeCashflow", "totalDebt", "debtToEquity", "beta",
            "dividendYield", "recommendationMean", "targetMeanPrice",
        ]
        snapshot["info"] = {k: info.get(k) for k in wanted_keys if k in info}
        snapshot["status"] = "ok" if snapshot["info"] else "empty"
        return snapshot
    except Exception as exc:
        snapshot["status"] = "error"
        snapshot["error"] = str(exc)
        return snapshot


def web_search(query: str, max_results: int = 5) -> List[SourceItem]:
    """DDGS ile web araması yapar. Paket/internet yoksa boş liste döner."""
    results: List[SourceItem] = []
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                title = item.get("title") or "Untitled"
                url = item.get("href") or item.get("url") or ""
                snippet = item.get("body") or item.get("snippet") or ""
                if url:
                    results.append(SourceItem(title=title, url=url, snippet=snippet, source_type="web"))
    except Exception as exc:
        results.append(
            SourceItem(
                title="Web search unavailable",
                url="",
                snippet=f"DDGS search failed or internet unavailable: {exc}",
                source_type="system",
            )
        )
    return results


def run_research_queries(queries, max_results_per_query: int = 4) -> List[SourceItem]:
    all_sources: List[SourceItem] = []
    seen = set()
    for q in queries:
        for source in web_search(q.query, max_results=max_results_per_query):
            key = source.url or f"{source.title}-{source.snippet[:30]}"
            if key in seen:
                continue
            seen.add(key)
            all_sources.append(source)
    return all_sources


def sec_company_lookup(ticker: str) -> Dict[str, Any]:
    """SEC company_tickers endpointinden basit CIK lookup yapar."""
    headers = {"User-Agent": "financial-agent-student-project contact@example.com"}
    output = {"ticker": ticker, "cik": None, "status": "not_loaded", "error": None}
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for _, row in data.items():
            if row.get("ticker", "").upper() == ticker.upper():
                output["cik"] = str(row.get("cik_str")).zfill(10)
                output["status"] = "ok"
                return output
        output["status"] = "not_found"
        return output
    except Exception as exc:
        output["status"] = "error"
        output["error"] = str(exc)
        return output

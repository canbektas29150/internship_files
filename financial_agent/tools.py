from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import requests
from schemas import ResearchSource

try:
    import yfinance as yf  # type: ignore
except Exception:
    yf = None


FRED_API_KEY: Optional[str] = None
SEC_USER_AGENT = "FinancialAgentCleanV2/1.0 contact: your-email@example.com"
MEMORY_FILE = Path("reports_memory.jsonl")


def company_profile(ticker: str) -> Dict[str, object]:
    if yf is None:
        return {"ticker": ticker, "name": ticker}
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency"),
        }
    except Exception as exc:
        return {"ticker": ticker, "name": ticker, "error": str(exc)}


def financial_metrics(ticker: str) -> Dict[str, object]:
    if yf is None:
        return {}
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            "revenue_growth": info.get("revenueGrowth"),
            "net_margin": info.get("profitMargins"),
            "free_cash_flow": info.get("freeCashflow"),
            "debt_equity": info.get("debtToEquity"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "market_cap": info.get("marketCap"),
        }
    except Exception:
        return {}


def _query_company_tokens(query: str) -> set[str]:
    q = re.sub(r"[^a-zA-Z0-9\.\s]", " ", query.lower())
    stop = {
        "latest", "earnings", "revenue", "margin", "outlook", "recent", "financial",
        "news", "risk", "performance", "sector", "macro", "trends", "sec", "10", "k",
        "factors", "inc", "corporation", "company", "stock"
    }
    return {t for t in q.split() if len(t) >= 3 and t not in stop}


def _is_good_source(source: ResearchSource) -> bool:
    text = f"{source.title} {source.summary} {source.url}".lower()
    query_tokens = _query_company_tokens(source.query)

    bad_phrases = [
        "outlook oturum açma",
        "microsoft 365",
        "login",
        "sign in",
        "ceic",
        "isimarkets",
        "all apple watch models",
    ]
    if any(bad in text for bad in bad_phrases):
        return False

    if query_tokens and not any(token in text for token in query_tokens):
        return False

    return bool(source.title.strip())


def news_search(query: str, limit: int = 4) -> List[ResearchSource]:
    try:
        from ddgs import DDGS  # type: ignore
    except Exception:
        return []
    try:
        out: List[ResearchSource] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max(limit * 3, 8)):
                source = ResearchSource(
                    query=query,
                    title=item.get("title", ""),
                    summary=item.get("body", ""),
                    url=item.get("href", ""),
                )
                if _is_good_source(source):
                    out.append(source)
                if len(out) >= limit:
                    break
        return out
    except Exception:
        return []
def _fred_latest(series_id: str) -> Optional[float]:
    params = {"series_id": series_id, "file_type": "json", "observation_start": "2019-01-01"}
    if FRED_API_KEY:
        params["api_key"] = FRED_API_KEY
    try:
        r = requests.get("https://api.stlouisfed.org/fred/series/observations", params=params, timeout=10)
        r.raise_for_status()
        vals = [float(x["value"]) for x in r.json().get("observations", []) if x.get("value") not in (None, ".")]
        return vals[-1] if vals else None
    except Exception:
        return None


def _worldbank_latest(country: str, indicator: str) -> Optional[float]:
    try:
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
        r = requests.get(url, params={"format": "json", "date": "2019:2026"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        vals = [float(x["value"]) for x in data[1] if x.get("value") is not None]
        return vals[-1] if vals else None
    except Exception:
        return None


def macro_score(sector: Optional[str], country_code: str = "USA") -> Dict[str, object]:
    interest = _fred_latest("DFF")
    inflation = _worldbank_latest(country_code, "FP.CPI.TOTL.ZG")
    growth = _worldbank_latest(country_code, "NY.GDP.MKTP.KD.ZG")

    interest_n = 4.0 if interest is None else interest
    inflation_n = 3.0 if inflation is None else inflation
    growth_n = 2.0 if growth is None else growth

    sector_l = (sector or "").lower()
    if "technology" in sector_l:
        sensitivity = {"interest": -1.0, "inflation": -0.5, "growth": 1.0}
    elif "financial" in sector_l:
        sensitivity = {"interest": 0.6, "inflation": -0.1, "growth": 0.5}
    elif "energy" in sector_l:
        sensitivity = {"interest": 0.1, "inflation": 0.4, "growth": 0.5}
    else:
        sensitivity = {"interest": -0.3, "inflation": -0.2, "growth": 0.6}

    score = 50 + 3 * sensitivity["interest"] * interest_n + 2 * sensitivity["inflation"] * inflation_n + 6 * sensitivity["growth"] * growth_n
    score = max(0.0, min(100.0, round(score, 1)))
    return {
        "score": score,
        "factors": {"interest_rate": interest, "inflation": inflation, "gdp_growth": growth},
        "sensitivity": sensitivity,
        "note": "Missing macro values use neutral fallback internally.",
    }


@lru_cache(maxsize=256)
def cik_from_ticker(ticker: str) -> Optional[str]:
    if "." in ticker:
        return None
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json", headers={"User-Agent": SEC_USER_AGENT}, timeout=10)
        r.raise_for_status()
        for item in r.json().values():
            if str(item.get("ticker", "")).upper() == ticker.upper():
                return str(item.get("cik_str")).zfill(10)
    except Exception:
        return None
    return None


def sec_risk_excerpt(ticker: str) -> Optional[str]:
    cik = cik_from_ticker(ticker)
    if not cik:
        return None
    try:
        sub = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers={"User-Agent": SEC_USER_AGENT}, timeout=10).json()
        recent = sub.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        for form, acc, doc in zip(forms, accessions, docs):
            if str(form).startswith("10-K"):
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
                text = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=12).text
                clean = re.sub(r"\s+", " ", text)
                idx = clean.lower().find("risk factors")
                return clean[idx:idx + 2200] if idx != -1 else clean[:1200]
    except Exception:
        return None
    return None


def load_previous(ticker: str) -> Optional[Dict[str, object]]:
    if not MEMORY_FILE.exists():
        return None
    rows = []
    for line in MEMORY_FILE.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if str(row.get("ticker", "")).upper() == ticker.upper():
                rows.append(row)
        except Exception:
            pass
    return rows[-1] if rows else None


def save_memory(ticker: str, investment: float, risk: float, summary: str) -> None:
    row = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "ticker": ticker,
        "investment": investment,
        "risk": risk,
        "summary": summary[:600],
    }
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_json(data: dict, path: str) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def export_excel(report: dict, path: str) -> None:
    try:
        import openpyxl  # type: ignore
    except Exception:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Company", report["company"]])
    ws.append(["Ticker", report["ticker"]])
    ws.append(["Investment Score", report["score"]["investment_score"]])
    ws.append(["Risk Score", report["score"]["risk_score"]])
    ws.append(["Risk Level", report["score"]["risk_level"]])
    ws.append(["Executive Summary", report["executive_summary"]])
    ws.append([])
    ws.append(["Positives"])
    for item in report["score"].get("positives", []):
        ws.append([item])
    ws.append([])
    ws.append(["Risks"])
    for item in report["score"].get("risks", []):
        ws.append([item])
    ws.append([])
    ws.append(["Sources"])
    for source in report.get("sources", []):
        ws.append([source.get("title"), source.get("url")])
    wb.save(path)

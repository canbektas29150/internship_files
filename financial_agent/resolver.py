from __future__ import annotations

import difflib
import re
from typing import List
from schemas import CompanyCandidate


COMPANIES = [
    ("Apple Inc.", "AAPL", ["apple", "apple inc", "iphone", "aapl"], "United States"),
    ("Microsoft Corporation", "MSFT", ["microsoft", "msft"], "United States"),
    ("Tesla Inc.", "TSLA", ["tesla", "tsla"], "United States"),
    ("NVIDIA Corporation", "NVDA", ["nvidia", "nvda", "nvdia"], "United States"),
    ("Alphabet Inc. / Google", "GOOGL", ["google", "alphabet", "googl"], "United States"),
    ("Amazon.com Inc.", "AMZN", ["amazon", "amzn"], "United States"),
    ("Meta Platforms", "META", ["meta", "facebook"], "United States"),
    ("Ford Motor Company", "F", ["ford", "ford motor"], "United States"),
    ("Ford Otosan", "FROTO.IS", ["ford otosan", "froto", "ford otomotiv"], "Türkiye"),
    ("Aselsan", "ASELS.IS", ["aselsan", "asels"], "Türkiye"),
    ("Turkish Airlines", "THYAO.IS", ["thy", "thyao", "turkish airlines", "türk hava yolları"], "Türkiye"),
    ("Şişecam", "SISE.IS", ["şişecam", "sisecam", "sise"], "Türkiye"),
    ("Koç Holding", "KCHOL.IS", ["koç holding", "koc holding", "kchol"], "Türkiye"),
    ("Tüpraş", "TUPRS.IS", ["tüpraş", "tupras", "tuprs"], "Türkiye"),
    ("Ethereum", "ETH-USD", ["ethereum", "eth", "ether"], "Crypto"),
    ("Bitcoin", "BTC-USD", ["bitcoin", "btc"], "Crypto"),
]

STOP_TICKERS = {"AI", "API", "PDF", "JSON", "SEC", "FRED", "GDP", "CEO", "LLM"}


def normalize(text: str) -> str:
    text = (text or "").lower()
    for old, new in {"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9\.\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_candidates(user_text: str, limit: int = 5) -> List[CompanyCandidate]:
    raw = user_text or ""
    norm = normalize(raw)
    results: List[CompanyCandidate] = []
    seen = set()

    alias_rows = []
    for label, ticker, aliases, country in COMPANIES:
        for alias in [label, ticker] + aliases:
            alias_rows.append((normalize(alias), label, ticker, country))

    # Alias/known-name first. This fixes APPLE -> AAPL instead of raw ticker APPLE.
    for alias_norm, label, ticker, country in alias_rows:
        if not alias_norm or ticker in seen:
            continue
        if norm == alias_norm or f" {alias_norm} " in f" {norm} ":
            source = "ticker_exact" if normalize(ticker) == alias_norm else "alias_match"
            confidence = 1.0 if source == "ticker_exact" else 0.97
            results.append(CompanyCandidate(label=label, ticker=ticker, country=country, confidence=confidence, source=source))
            seen.add(ticker)

    # Known ticker exact.
    for ticker_word in re.findall(r"\b[A-Z]{1,8}(?:\.IS|-USD)?\b", raw.upper()):
        if ticker_word in STOP_TICKERS:
            continue
        match = next((c for c in COMPANIES if c[1].upper() == ticker_word), None)
        if match and match[1] not in seen:
            results.append(CompanyCandidate(label=match[0], ticker=match[1], country=match[3], confidence=1.0, source="ticker_exact"))
            seen.add(match[1])

    # Fuzzy typo match.
    alias_names = [x[0] for x in alias_rows]
    for token in [norm] + norm.split():
        if len(token) < 4:
            continue
        for close in difflib.get_close_matches(token, alias_names, n=2, cutoff=0.84):
            _, label, ticker, country = next(x for x in alias_rows if x[0] == close)
            if ticker not in seen:
                results.append(CompanyCandidate(label=label, ticker=ticker, country=country, confidence=0.74, source="fuzzy_match"))
                seen.add(ticker)

    # Raw ticker fallback only if no known company matched.
    if not results:
        for ticker_word in re.findall(r"\b[A-Z]{1,8}(?:\.IS|-USD)?\b", raw.upper()):
            if ticker_word not in STOP_TICKERS:
                results.append(CompanyCandidate(label=f"Ticker: {ticker_word}", ticker=ticker_word, confidence=0.80, source="ticker_raw"))
                break

    return sorted(results, key=lambda x: x.confidence, reverse=True)[:limit]

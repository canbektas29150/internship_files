from __future__ import annotations

import re
from typing import Dict, List
from schemas import CompanyCandidate


KNOWN_COMPANIES: Dict[str, CompanyCandidate] = {
    "apple": CompanyCandidate("Apple Inc.", "AAPL", 0.98, "Matched known company alias."),
    "aapl": CompanyCandidate("Apple Inc.", "AAPL", 0.98, "Matched ticker alias."),
    "ibm": CompanyCandidate("International Business Machines Corporation", "IBM", 0.98, "Matched known company alias."),
    "international business machines": CompanyCandidate("International Business Machines Corporation", "IBM", 0.98, "Matched long company name."),
    "microsoft": CompanyCandidate("Microsoft Corporation", "MSFT", 0.98, "Matched known company alias."),
    "msft": CompanyCandidate("Microsoft Corporation", "MSFT", 0.98, "Matched ticker alias."),
    "nvidia": CompanyCandidate("NVIDIA Corporation", "NVDA", 0.98, "Matched known company alias."),
    "nvda": CompanyCandidate("NVIDIA Corporation", "NVDA", 0.98, "Matched ticker alias."),
    "tesla": CompanyCandidate("Tesla, Inc.", "TSLA", 0.98, "Matched known company alias."),
    "tsla": CompanyCandidate("Tesla, Inc.", "TSLA", 0.98, "Matched ticker alias."),
    "amazon": CompanyCandidate("Amazon.com, Inc.", "AMZN", 0.98, "Matched known company alias."),
    "amzn": CompanyCandidate("Amazon.com, Inc.", "AMZN", 0.98, "Matched ticker alias."),
    "google": CompanyCandidate("Alphabet Inc.", "GOOGL", 0.95, "Matched common company alias."),
    "alphabet": CompanyCandidate("Alphabet Inc.", "GOOGL", 0.98, "Matched known company alias."),
    "meta": CompanyCandidate("Meta Platforms, Inc.", "META", 0.98, "Matched known company alias."),
    "palantir": CompanyCandidate("Palantir Technologies Inc.", "PLTR", 0.98, "Matched known company alias."),
    "pltr": CompanyCandidate("Palantir Technologies Inc.", "PLTR", 0.98, "Matched ticker alias."),
    "ford": CompanyCandidate("Ford Motor Company", "F", 0.95, "Matched known company alias."),
    "bitcoin": CompanyCandidate("Bitcoin USD", "BTC-USD", 0.95, "Matched crypto alias."),
    "btc": CompanyCandidate("Bitcoin USD", "BTC-USD", 0.95, "Matched crypto alias."),
    "ethereum": CompanyCandidate("Ethereum USD", "ETH-USD", 0.95, "Matched crypto alias."),
    "eth": CompanyCandidate("Ethereum USD", "ETH-USD", 0.95, "Matched crypto alias."),
}


def resolve_company(prompt: str) -> CompanyCandidate:
    text = prompt.lower()

    # Long aliases first, so "international business machines" wins over shorter tokens.
    for alias in sorted(KNOWN_COMPANIES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            return KNOWN_COMPANIES[alias]

    ticker_match = re.search(r"\b[A-Z]{1,5}(?:-[A-Z]{3})?\b", prompt)
    if ticker_match:
        ticker = ticker_match.group(0)
        return CompanyCandidate(ticker, ticker, 0.70, "Detected ticker-like symbol from prompt.")

    first_word = re.sub(r"[^a-zA-Z0-9.-]", "", prompt.split()[0]) if prompt.split() else "UNKNOWN"
    fallback = first_word.upper() if first_word else "UNKNOWN"
    return CompanyCandidate(fallback, fallback, 0.35, "Fallback: first token treated as ticker. Add to KNOWN_COMPANIES for better resolution.")

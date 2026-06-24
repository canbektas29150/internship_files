from __future__ import annotations

import re
from typing import List
from resolver import resolve_company
from schemas import ResearchPlan, ResearchQuery


def detect_timeframe(prompt: str) -> str:
    text = prompt.lower()
    if any(x in text for x in ["3. çeyrek", "q3", "third quarter", "3rd quarter"]):
        return "Q3 / third quarter"
    if any(x in text for x in ["2. çeyrek", "q2", "second quarter"]):
        return "Q2 / second quarter"
    if any(x in text for x in ["4. çeyrek", "q4", "fourth quarter"]):
        return "Q4 / fourth quarter"
    if any(x in text for x in ["orta vade", "orta vadede", "medium term"]):
        return "medium term"
    if any(x in text for x in ["kısa vade", "short term", "yakın dönem"]):
        return "short term"
    if any(x in text for x in ["uzun vade", "long term"]):
        return "long term"
    return "general / next reporting periods"


def detect_intent(prompt: str) -> str:
    text = prompt.lower()
    if any(x in text for x in ["risk", "tehlike", "downside", "kötü"]):
        return "risk_analysis"
    if any(x in text for x in ["yatırım", "investment", "alınır mı", "buy", "score"]):
        return "investment_analysis"
    if any(x in text for x in ["çeyrek", "quarter", "q1", "q2", "q3", "q4", "nasıl bir şey yapar"]):
        return "quarterly_outlook"
    if any(x in text for x in ["yatırımlar", "acquisition", "satın alma", "arge", "r&d", "ai"]):
        return "strategic_impact"
    if any(x in text for x in ["haber", "news", "son gelişme"]):
        return "news_impact"
    return "general_company_analysis"


def build_questions(prompt: str, intent: str, company_name: str, ticker: str, timeframe: str) -> List[str]:
    base = [
        f"{company_name} ({ticker}) için kullanıcının sorduğu ana soruya kısa cevap ver.",
        "Finansal metriklerde büyüme, kârlılık, nakit akımı ve değerleme tarafını kontrol et.",
        "Son haberlerde olumlu/olumsuz katalizörleri ayır.",
        "Risk skorunun hangi metriklerden oluştuğunu açıkla.",
    ]
    if intent == "quarterly_outlook":
        base.insert(1, f"{timeframe} için gelir, marj, ürün/segment ve beklenti katalizörlerini incele.")
    if intent == "strategic_impact":
        base.insert(1, "Şirket yatırımlarının gelir, marj, rekabet avantajı ve risklere orta vadeli etkisini incele.")
    if intent == "risk_analysis":
        base.insert(1, "Riskleri makro, rekabet, regülasyon, bilanço ve haber akışı olarak ayır.")
    return base


def generate_research_plan(prompt: str) -> ResearchPlan:
    company = resolve_company(prompt)
    intent = detect_intent(prompt)
    timeframe = detect_timeframe(prompt)
    qname = company.name
    ticker = company.ticker

    queries = [
        ResearchQuery(
            topic="company_news",
            query=f"{qname} {ticker} latest news {timeframe} outlook",
            source_type="web",
        ),
        ResearchQuery(
            topic="earnings_guidance",
            query=f"{qname} {ticker} earnings guidance revenue margin {timeframe}",
            source_type="web",
        ),
        ResearchQuery(
            topic="risk_factors",
            query=f"{qname} {ticker} risk factors competition regulation SEC",
            source_type="web",
        ),
    ]

    if intent == "quarterly_outlook":
        queries.extend([
            ResearchQuery("quarter_specific", f"{qname} {ticker} Q3 forecast analyst expectations", "web"),
            ResearchQuery("segment_drivers", f"{qname} {ticker} Q3 drivers products services margins", "web"),
        ])

    if intent == "strategic_impact":
        queries.extend([
            ResearchQuery("strategic_investments", f"{qname} {ticker} investments acquisitions AI cloud strategy impact", "web"),
            ResearchQuery("medium_term_effect", f"{qname} {ticker} medium term growth margin free cash flow investments", "web"),
        ])

    questions = build_questions(prompt, intent, qname, ticker, timeframe)
    return ResearchPlan(
        original_prompt=prompt,
        intent=intent,
        timeframe=timeframe,
        company=company,
        questions_to_answer=questions,
        queries=queries,
    )

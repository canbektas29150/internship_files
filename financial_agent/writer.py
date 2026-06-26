from __future__ import annotations

import re
from typing import Any, Dict, List

from schemas import AnalystFinding, ResearchPlan, ScoreCard, SourceItem
from llm_client import call_ollama


def build_executive_answer(plan: ResearchPlan, investment: ScoreCard, risk: ScoreCard, sources: List[SourceItem]) -> str:
    """Önce prompta doğrudan cevap verir. Ollama varsa onu dener, yoksa fallback."""
    source_lines = "\n".join(f"- {s.title}: {s.snippet[:220]}" for s in sources[:6] if s.title)
    user_prompt = f"""
Kullanıcı promptu: {plan.original_prompt}
Şirket: {plan.company.name} ({plan.company.ticker})
Intent: {plan.intent}
Timeframe: {plan.timeframe}
Investment Score: {investment.total_score}/100
Risk Score: {risk.total_score}/10
Kaynak özetleri:
{source_lines}

Önce kullanıcının sorusuna 1 kısa paragrafla doğrudan cevap ver. Sonra 3 madde halinde nedenlerini yaz.
Yatırım tavsiyesi verme.
"""

    llm_answer = call_ollama(
        system_prompt="Sen finansal araştırma destek ajanısın. OpenAI API kullanmazsın. Cevapların Türkçe, net ve veri odaklıdır.",
        user_prompt=user_prompt,
    )
    if llm_answer:
        return llm_answer

    company = plan.company.name
    ticker = plan.company.ticker
    if plan.intent == "quarterly_outlook":
        return (
            f"{company} ({ticker}) için {plan.timeframe} görünümü, canlı veri kaynaklarından gelen finansal metrikler "
            f"ve haber akışıyla birlikte değerlendirildiğinde investment score {investment.total_score}/100, "
            f"risk score {risk.total_score}/10 seviyesinde görünüyor. Eğer gelir büyümesi, marjlar ve ürün/segment "
            "katalizörleri güçlü kalırsa olumlu bir çeyrek ihtimali artar; ancak beklenti yüksekliği, makro baskı ve "
            "haber akışındaki negatif sürprizler sonucu zayıflatabilir."
        )

    if plan.intent == "strategic_impact":
        return (
            f"{company} ({ticker}) için stratejik yatırım etkisi orta vadede gelir büyümesi, marj kalitesi ve rekabet "
            f"avantajı üzerinden pozitif okunabilir; mevcut hesapta investment score {investment.total_score}/100, "
            f"risk score {risk.total_score}/10. Ana mesele, bu yatırımların gerçek nakit akışına dönüşme hızı ve "
            "entegrasyon/rekabet risklerinin kontrol altında kalmasıdır."
        )

    if plan.intent == "risk_analysis":
        return (
            f"{company} ({ticker}) için risk tarafında skor {risk.total_score}/10. Bu skor; bilanço, beta, haber akışı, "
            "SEC/raporlama görünürlüğü ve veri bulunabilirliği metriklerinden hesaplandı. En kritik nokta, eksik veya "
            "zayıf veri varsa belirsizliğin artmasıdır."
        )

    return (
        f"{company} ({ticker}) için prompta göre genel analiz üretildi. Investment score {investment.total_score}/100, "
        f"risk score {risk.total_score}/10. Daha güvenilir yorum için finansal metrikler, haberler, beklentiler ve "
        "risk faktörleri birlikte okunmalıdır."
    )


def _descriptor(score: float, positive: bool = True) -> str:
    if positive:
        if score >= 70:
            return "güçlü"
        if score >= 50:
            return "orta"
        return "zayıf"
    if score >= 70:
        return "yüksek"
    if score >= 50:
        return "orta"
    return "düşük"


def build_analyst_findings(plan: ResearchPlan, investment: ScoreCard, risk: ScoreCard, sources: List[SourceItem]) -> List[AnalystFinding]:
    top_inv = sorted(investment.metrics, key=lambda m: m.score * m.weight, reverse=True)[:3]
    worst_inv = sorted(investment.metrics, key=lambda m: m.score * m.weight)[:2]
    top_risk = sorted(risk.metrics, key=lambda m: m.score * m.weight, reverse=True)[:3]
    safest_risk = sorted(risk.metrics, key=lambda m: m.score * m.weight)[:2]

    planner_queries = [q.query for q in plan.queries[:4]]
    source_titles = [s.title for s in sources[:4] if s.title and s.source_type != "system"]
    system_sources = [s for s in sources if s.source_type == "system"]

    return [
        AnalystFinding(
            role="Planner Agent",
            assessment=(
                f"Prompt '{plan.intent}' olarak sınıflandırıldı; zaman ufku '{plan.timeframe}'. "
                f"Şirket çözümü: {plan.company.name} ({plan.company.ticker}), güven={plan.company.confidence}."
            ),
            positives=[
                f"Üretilen araştırma sorusu sayısı: {len(plan.questions_to_answer)}",
                f"Üretilen web sorgusu sayısı: {len(plan.queries)}",
                *planner_queries,
            ],
            risks=[
                "Prompt çok kısa veya şirket adı belirsizse resolver yanlış ticker seçebilir.",
                "Intent kural tabanlı belirlendiği için çok karmaşık promptlarda elle kontrol gerekebilir.",
            ],
        ),
        AnalystFinding(
            role="Financial Analyst Agent",
            assessment=(
                "Investment skoru; büyüme, kârlılık, serbest nakit akışı, değerleme, kaynak kapsamı ve stratejik momentum metriklerinden hesaplandı."
            ),
            positives=[
                f"{m.name}: {m.value} → {_descriptor(m.score, positive=True)} katkı | score={m.score}, weight={m.weight}, source={m.source}"
                for m in top_inv
            ],
            risks=[
                f"Zayıf/eksik metrik: {m.name}: {m.value} | score={m.score}, source={m.source}"
                for m in worst_inv
            ] + ["Eksik yfinance alanları varsa ilgili metrikler nötr skorla hesaplanır; bu confidence değerini düşürür."],
        ),
        AnalystFinding(
            role="Risk Analyst Agent",
            assessment=(
                "Risk skoru 1–10 ölçeğinde hesaplandı; yüksek skor daha yüksek risk anlamına gelir. Risk; kaldıraç, beta, veri eksikliği, SEC görünürlüğü ve haber yoğunluğundan oluşur."
            ),
            positives=[
                f"Risk sürücüsü: {m.name}: {m.value} → {_descriptor(m.score, positive=False)} risk | raw score={m.score}, weight={m.weight}, source={m.source}"
                for m in top_risk
            ],
            risks=[
                f"Görece düşük risk alanı: {m.name}: {m.value} | raw score={m.score}"
                for m in safest_risk
            ] + ["SEC veya finansal veri hatası varsa risk skoru belirsizlik primi içerir."],
        ),
        AnalystFinding(
            role="News Research Agent",
            assessment=(
                f"Araştırma tarafında {len(sources)} kaynak öğesi toplandı. Sources sekmesinde linkler tıklanabilir olarak gösterilir."
            ),
            positives=(source_titles if source_titles else ["Kullanılabilir canlı haber kaynağı bulunamadı."]),
            risks=(
                [f"Search/tool uyarısı: {s.snippet}" for s in system_sources[:2]]
                if system_sources else
                ["Haber başlıkları tek başına yeterli değildir; önemli claim'ler kaynağın içinde doğrulanmalıdır."]
            ),
        ),
    ]


def build_report_summary(plan: ResearchPlan, investment: ScoreCard, risk: ScoreCard, sources: List[SourceItem]) -> str:
    metric_text = "; ".join(f"{m.name}={m.value} ({m.score})" for m in investment.metrics[:4])
    risk_text = "; ".join(f"{m.name}={m.value} ({m.score})" for m in risk.metrics[:4])
    source_text = "; ".join(s.title for s in sources[:5] if s.title)

    return (
        f"{plan.company.name} ({plan.company.ticker}) için analiz, kullanıcının '{plan.original_prompt}' sorusuna göre "
        f"oluşturuldu. Planlayıcı intent'i '{plan.intent}', zaman ufkunu '{plan.timeframe}' olarak belirledi. "
        f"Investment score {investment.total_score}/100 hesaplandı; ana yatırım metrikleri: {metric_text}. "
        f"Risk score {risk.total_score}/10 hesaplandı; ana risk metrikleri: {risk_text}. "
        f"Araştırma tarafında kullanılan başlıca kaynak başlıkları: {source_text if source_text else 'canlı kaynak bulunamadı'}. "
        "Bu analiz yatırım tavsiyesi değil, araştırma desteğidir."
    )


def validate_final_answer(
    executive_answer: str,
    plan: ResearchPlan,
    investment: ScoreCard,
    risk: ScoreCard,
    sources: List[SourceItem],
) -> Dict[str, Any]:
    """Simple claim → evidence validation for the generated answer.

    This is deliberately transparent and rule-based. It does not claim to be a
    complete fact checker. It checks whether the final answer makes claims that
    are supported by internal evidence objects or collected sources.
    """
    lower = executive_answer.lower()
    source_available = any(s.url for s in sources)
    checks: List[Dict[str, Any]] = []

    def add_claim(claim: str, supported: bool, evidence: str, warning: str = "") -> None:
        checks.append({
            "claim": claim,
            "supported": supported,
            "evidence": evidence,
            "warning": warning,
        })

    add_claim(
        f"Company resolved as {plan.company.name} ({plan.company.ticker})",
        bool(plan.company.ticker and plan.company.confidence >= 0.6),
        f"resolver confidence={plan.company.confidence}; reason={plan.company.reason}",
        "low resolver confidence" if plan.company.confidence < 0.6 else "",
    )
    if "investment score" in lower:
        add_claim(
            f"Investment score = {investment.total_score}/100",
            bool(investment.metrics),
            f"{len(investment.metrics)} metrics in scoring.py",
        )
    if "risk score" in lower or "risk" in lower:
        add_claim(
            f"Risk score = {risk.total_score}/10",
            bool(risk.metrics),
            f"{len(risk.metrics)} metrics in scoring.py",
        )
    if re.search(r"haber|news|kaynak|source", lower):
        add_claim(
            "Answer references news/source context",
            source_available,
            f"{len([s for s in sources if s.url])} URL-backed source items",
            "no URL-backed source found" if not source_available else "",
        )

    supported_count = sum(1 for c in checks if c["supported"])
    unsupported_count = len(checks) - supported_count
    confidence = round(supported_count / max(1, len(checks)), 3)
    return {
        "supported_claims": supported_count,
        "unsupported_claims": unsupported_count,
        "confidence": confidence,
        "claim_checks": checks,
    }

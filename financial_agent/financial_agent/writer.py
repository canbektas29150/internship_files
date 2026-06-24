from __future__ import annotations

from typing import List
from schemas import AnalystFinding, ResearchPlan, ScoreCard, SourceItem
from llm_client import call_ollama


def build_executive_answer(plan: ResearchPlan, investment: ScoreCard, risk: ScoreCard, sources: List[SourceItem]) -> str:
    """
    Kullanıcının sorusuna kısa ve doğrudan bir cevap üretir.

    Bu fonksiyon önce Ollama modeline bir istek gönderir; model yanıt vermezse
    fallback olarak basit kural tabanlı bir cevap oluşturur. Executive
    cevap, yatırım tavsiyesi vermeksizin sorulan soruyu yanıtlar ve temel
    gerekçeleri listeler. Risk skoru artık 1–10 ölçeğinde raporlanır.
    """
    # Derlenen kaynak başlıklarını ve özetleri birleştir
    source_lines = "\n".join(
        f"- {s.title}: {s.snippet[:220]}" for s in sources[:6] if s.title
    )
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

    # If Ollama is available it will produce a more natural-language answer
    llm_answer = call_ollama(
        system_prompt="Sen finansal araştırma destek ajanısın. OpenAI API kullanmazsın. Cevapların Türkçe, net ve veri odaklıdır.",
        user_prompt=user_prompt,
    )
    if llm_answer:
        return llm_answer

    # Fallback responses for when Ollama is unavailable
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


def build_analyst_findings(
    plan: ResearchPlan,
    investment: ScoreCard,
    risk: ScoreCard,
    sources: List[SourceItem],
) -> List[AnalystFinding]:
    """
    Derinlemesine analist bulguları üretir.

    Bu fonksiyon, planlama aşaması, finansal analiz, risk değerlendirmesi ve
    haber araştırması için ayrı bulgular döndürür. Her bulgu; kısa bir
    değerlendirme, olumlu/yararlı sinyaller ve potansiyel riskler içerir.
    Metinler kullanıcı tarafından daha kolay anlaşılabilecek şekilde
    hazırlanmıştır.
    """
    findings: List[AnalystFinding] = []

    # 1. Planner Agent
    planner_positives: List[str] = []
    # özet: intent ve timeframe
    planner_positives.append(f"Intent: {plan.intent}")
    planner_positives.append(f"Timeframe: {plan.timeframe}")
    # ilk birkaç sorguyu göster
    if plan.queries:
        sample_queries = ", ".join(q.query for q in plan.queries[:3])
        planner_positives.append(f"Örnek sorgular: {sample_queries}")
    planner_risks = [
        "Belirsiz veya çok kısa bir prompt, şirket/ticker çözümünü ve intent belirlemeyi zorlaştırabilir."
    ]
    findings.append(
        AnalystFinding(
            role="Planner Agent",
            assessment=(
                f"Soru, '{plan.intent}' intenti ve '{plan.timeframe}' zaman ufku olarak sınıflandırıldı. "
                f"Toplam {len(plan.queries)} adet araştırma sorgusu üretildi."
            ),
            positives=planner_positives,
            risks=planner_risks,
        )
    )

    # 2. Financial Analyst Agent
    # En yüksek katkı yapan 3 yatırım metriğini bul
    top_inv = sorted(investment.metrics, key=lambda m: m.score * m.weight, reverse=True)[:3]
    fin_positives: List[str] = []
    for m in top_inv:
        # Basit niteliklendirme: yüksek / orta / düşük katkı
        if m.score >= 70:
            descriptor = "yüksek"
        elif m.score >= 50:
            descriptor = "orta"
        else:
            descriptor = "düşük"
        fin_positives.append(
            f"{m.name} ({m.value}): {descriptor} katkı (score={m.score}, weight={m.weight})"
        )
    # En zayıf metrikleri risk kısmında belirt
    # Risk olarak en düşük skor * ağırlık değerine sahip metriği ele al
    worst_inv = min(investment.metrics, key=lambda m: m.score * m.weight)
    fin_risks: List[str] = []
    fin_risks.append(
        f"{worst_inv.name} ({worst_inv.value}): performans zayıf (score={worst_inv.score}, weight={worst_inv.weight})"
    )
    fin_risks.append(
        "yfinance canlı veri döndürmezse veya veri eksikse yatırım metriklerinin güvenilirliği düşer."
    )
    findings.append(
        AnalystFinding(
            role="Financial Analyst Agent",
            assessment=(
                "Investment skoru; gelir büyümesi, kârlılık, nakit akışı ve değerleme gibi metriklerin ağırlıklı ortalaması olarak hesaplandı."
            ),
            positives=fin_positives,
            risks=fin_risks,
        )
    )

    # 3. Risk Analyst Agent
    top_risk = sorted(risk.metrics, key=lambda m: m.score * m.weight, reverse=True)[:3]
    risk_positives: List[str] = []
    for m in top_risk:
        if m.score >= 70:
            descriptor = "yüksek"
        elif m.score >= 50:
            descriptor = "orta"
        else:
            descriptor = "düşük"
        risk_positives.append(
            f"{m.name} ({m.value}): {descriptor} risk (score={m.score}, weight={m.weight})"
        )
    # En düşük riske sahip metriği bul
    safest = min(risk.metrics, key=lambda m: m.score * m.weight)
    risk_risks: List[str] = []
    risk_risks.append(
        f"{safest.name} ({safest.value}): risk düşük (score={safest.score}, weight={safest.weight})"
    )
    # Ek risk notu
    if risk.total_score > 7:
        risk_risks.append("Genel risk skoru yüksek; kaldıraç, piyasa oynaklığı veya verilerin sınırlılığı endişe kaynağı.")
    risk_risks.append(
        "Eksik veri veya SEC/raporlama şeffaflığının olmaması risk belirsizliğini artırır."
    )
    findings.append(
        AnalystFinding(
            role="Risk Analyst Agent",
            assessment=(
                "Risk skoru; kaldıraç, piyasa oynaklığı, veri bulunabilirliği, SEC şeffaflığı ve haber yoğunluğu gibi unsurlardan hesaplandı."
            ),
            positives=risk_positives,
            risks=risk_risks,
        )
    )

    # 4. News Research Agent
    news_positives: List[str] = []
    news_risks: List[str] = []
    if sources:
        for s in sources[:3]:
            title = s.title or "Untitled"
            snippet = s.snippet.strip() if s.snippet else ""
            summary = snippet[:160] + ("..." if len(snippet) > 160 else "")
            news_positives.append(f"{title}: {summary}")
        # If there are more sources than we summarised, mention the count
        if len(sources) > 3:
            news_positives.append(f"+ {len(sources) - 3} ek kaynak")
        news_risks.append(
            "Toplanan haberler güncel olmayabilir veya başlıklar yanıltıcı olabilir; ayrıntılı okumak gerekir."
        )
    else:
        news_risks.append("DDGS veya internet çalışmadığı için haber analizi yapılamadı.")
    findings.append(
        AnalystFinding(
            role="News Research Agent",
            assessment=(
                f"Haber aramasından {len(sources)} adet kaynak elde edildi ve rapora yansıtıldı."
            ),
            positives=news_positives,
            risks=news_risks,
        )
    )

    return findings


def build_report_summary(
    plan: ResearchPlan,
    investment: ScoreCard,
    risk: ScoreCard,
    sources: List[SourceItem],
) -> str:
    """
    Raporun kısa özetini üret.

    Bu özet, planlama sonuçlarını, yatırım ve risk skorlarını ve kullanılan
    başlıca kaynakları özetler. Risk skoru 1–10 ölçeğinde raporlanır.
    """
    metric_text = "; ".join(
        f"{m.name}={m.value} (score={m.score})" for m in investment.metrics[:4]
    )
    risk_text = "; ".join(
        f"{m.name}={m.value} (score={m.score})" for m in risk.metrics[:4]
    )
    source_titles = [s.title for s in sources[:5] if s.title]
    source_text = "; ".join(source_titles) if source_titles else "canlı kaynak bulunamadı"
    return (
        f"{plan.company.name} ({plan.company.ticker}) için analiz, kullanıcının '{plan.original_prompt}' sorusuna göre "
        f"oluşturuldu. Planlayıcı intent'i '{plan.intent}', zaman ufkunu '{plan.timeframe}' olarak belirledi. "
        f"Investment score {investment.total_score}/100 hesaplandı; ana yatırım metrikleri: {metric_text}. "
        f"Risk score {risk.total_score}/10 hesaplandı; ana risk metrikleri: {risk_text}. "
        f"Araştırma tarafında kullanılan başlıca kaynak başlıkları: {source_text}. "
        "Bu analiz yatırım tavsiyesi değil, araştırma desteğidir."
    )

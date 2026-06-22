from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional

from schemas import AnalystFinding, FinalReport, ResearchPlan, ScoreSummary, TraceStep, VerificationResult
from tools import company_profile, export_excel, export_json, financial_metrics, load_previous, macro_score, news_search, save_memory, sec_risk_excerpt

try:
    from agents import Agent, Runner, function_tool, gen_trace_id, trace  # type: ignore
except Exception:
    Agent = Runner = function_tool = gen_trace_id = trace = None


def sdk_enabled() -> bool:
    return Agent is not None and Runner is not None and bool(os.getenv("OPENAI_API_KEY"))


def make_plan(prompt: str, company: str, ticker: str) -> ResearchPlan:
    p = (prompt or "").lower()
    objective = "balanced company research"
    focus = ["fundamentals", "macro", "sec_risk", "news"]
    if "risk" in p or "due diligence" in p or "dd" in p:
        objective = "risk-focused due diligence"
        focus = ["sec_risk", "news", "macro", "fundamentals"]
    elif "macro" in p or "makro" in p:
        objective = "macro-sensitive company research"
        focus = ["macro", "fundamentals", "news", "sec_risk"]
    elif "valuation" in p or "değerleme" in p:
        objective = "valuation-focused company research"
        focus = ["fundamentals", "news", "macro", "sec_risk"]

    search_name = company.replace("Ticker: ", "").strip()
    queries = [
        f"{search_name} {ticker} latest earnings revenue margin outlook",
        f"{search_name} {ticker} recent financial news risk performance",
        f"{search_name} {ticker} sector outlook macro trends",
    ]
    if "sec_risk" in focus:
        queries.append(f"{search_name} {ticker} SEC 10-K risk factors")

    return ResearchPlan(
        company=company,
        ticker=ticker,
        objective=objective,
        focus_areas=focus,
        queries=queries,
        tools=["financial_metrics", "macro_score", "sec_edgar", "news_search", "writer", "verifier"],
    )


async def collect_data(plan: ResearchPlan) -> Dict[str, object]:
    profile_task = asyncio.to_thread(company_profile, plan.ticker)
    financials_task = asyncio.to_thread(financial_metrics, plan.ticker)
    sec_task = asyncio.to_thread(sec_risk_excerpt, plan.ticker)
    news_tasks = [asyncio.to_thread(news_search, query, 3) for query in plan.queries]

    profile, financials, sec_excerpt, *news_results = await asyncio.gather(profile_task, financials_task, sec_task, *news_tasks)
    sector = profile.get("sector") if isinstance(profile, dict) else None
    macro = await asyncio.to_thread(macro_score, sector)

    sources = []
    for group in news_results:
        sources.extend(group)

    # Deduplicate by URL/title.
    seen = set()
    clean_sources = []
    for source in sources:
        key = source.url or source.title
        if key and key not in seen:
            seen.add(key)
            clean_sources.append(source)

    return {
        "profile": profile,
        "financials": financials,
        "sec_excerpt": sec_excerpt,
        "macro": macro,
        "sources": clean_sources[:10],
    }


def fundamentals_finding(data: Dict[str, object]) -> AnalystFinding:
    fin = data.get("financials", {}) or {}
    positives, risks = [], []

    rg = fin.get("revenue_growth")
    margin = fin.get("net_margin")
    pe = fin.get("pe_ratio")
    fcf = fin.get("free_cash_flow")

    if isinstance(rg, (int, float)):
        positives.append("Revenue growth is positive." if rg > 0 else "Revenue growth data is negative or weak.")
        if rg < 0:
            risks.append("Negative revenue growth.")
    if isinstance(margin, (int, float)):
        positives.append("Net margin is healthy." if margin > 0.15 else "Net margin is not clearly strong.")
        if margin < 0.05:
            risks.append("Weak profitability margin.")
    if isinstance(pe, (int, float)) and pe > 45:
        risks.append("Elevated P/E valuation.")
    if isinstance(fcf, (int, float)) and fcf > 0:
        positives.append("Free cash flow is positive.")

    return AnalystFinding(
        name="Fundamentals Analyst",
        summary="Reviewed growth, profitability, cash flow and valuation metrics.",
        positives=positives[:4],
        risks=risks[:4],
        data=fin,
    )


def macro_finding(data: Dict[str, object]) -> AnalystFinding:
    macro = data.get("macro", {}) or {}
    score = macro.get("score", 50)
    positives, risks = [], []
    if score >= 65:
        positives.append("Macro backdrop appears supportive for the detected sector.")
    elif score < 40:
        risks.append("Macro backdrop appears challenging for the detected sector.")
    else:
        positives.append("Macro backdrop is broadly neutral.")
    return AnalystFinding(
        name="Macro Analyst",
        summary=f"Macro score is {score}/100 using interest rate, inflation and GDP growth inputs.",
        positives=positives,
        risks=risks,
        data=macro,
    )


def sec_finding(data: Dict[str, object]) -> AnalystFinding:
    sec = data.get("sec_excerpt")
    if not sec:
        return AnalystFinding(name="SEC Risk Analyst", summary="SEC 10-K risk excerpt is unavailable or not applicable.", risks=["SEC filing data was not available for this ticker."])
    text = str(sec).lower()
    risks = []
    for word in ["competition", "regulation", "litigation", "supply chain", "cybersecurity", "inflation"]:
        if word in text:
            risks.append(f"SEC risk section mentions {word}.")
    return AnalystFinding(name="SEC Risk Analyst", summary="SEC risk excerpt was collected and reviewed.", risks=risks[:5], data={"excerpt": str(sec)[:700]})


def news_finding(data: Dict[str, object]) -> AnalystFinding:
    sources = data.get("sources", []) or []
    text = " ".join((s.title + " " + s.summary) for s in sources).lower()
    positives, risks = [], []
    if any(w in text for w in ["growth", "beat", "record", "upgrade", "strong"]):
        positives.append("Recent sources include positive growth/performance signals.")
    if any(w in text for w in ["lawsuit", "probe", "fine", "investigation", "downgrade", "decline"]):
        risks.append("Recent sources include negative event or legal risk signals.")
    if not positives and not risks:
        positives.append("Recent source signal is mixed or neutral.")
    return AnalystFinding(name="News Analyst", summary=f"Reviewed {len(sources)} recent search sources.", positives=positives, risks=risks, data={"source_count": len(sources)})


def compute_score(findings: List[AnalystFinding], data: Dict[str, object]) -> ScoreSummary:
    investment = 50.0
    risk = 35.0
    positives, risks = [], []

    for finding in findings:
        positives.extend(finding.positives)
        risks.extend(finding.risks)

    fin = data.get("financials", {}) or {}
    macro = data.get("macro", {}) or {}

    def num(v, default=None):
        try:
            return float(v) if v is not None else default
        except Exception:
            return default

    rg = num(fin.get("revenue_growth"))
    margin = num(fin.get("net_margin"))
    pe = num(fin.get("pe_ratio"))
    macro_s = num(macro.get("score"), 50)

    if rg is not None and rg > 0.10:
        investment += 10
    if margin is not None and margin > 0.15:
        investment += 8
    if pe is not None and pe > 45:
        risk += 8
        investment -= 5
    if macro_s >= 65:
        investment += 5
    elif macro_s < 40:
        risk += 8

    risk += min(12, len(risks) * 3)
    investment += min(10, len(positives) * 2)

    investment = max(0, min(100, round(investment, 1)))
    risk = max(0, min(100, round(risk, 1)))
    level = "Very High" if risk >= 75 else "High" if risk >= 55 else "Medium" if risk >= 30 else "Low"

    return ScoreSummary(investment_score=investment, risk_score=risk, risk_level=level, positives=positives[:5], risks=risks[:5])


def write_summary(company: str, ticker: str, score: ScoreSummary, findings: List[AnalystFinding], source_count: int) -> str:
    pos = "; ".join(score.positives[:3]) if score.positives else "available data does not show a strong positive signal"
    risk = "; ".join(score.risks[:3]) if score.risks else "available data does not show a dominant risk signal"
    return (
        f"**{company} ({ticker})** was reviewed using financial metrics, macro indicators, SEC availability and recent research sources.\n\n"
        f"The current **Investment Score is {score.investment_score}/100** and the **Risk Score is {score.risk_score}/100 ({score.risk_level})**.\n\n"
        f"**Main positives:** {pos}.\n\n"
        f"**Main risks:** {risk}.\n\n"
        f"The summary is based on {len(findings)} analyst modules and {source_count} filtered research sources. "
        "This output is for research support only and is not investment advice."
    )


def verify_report(summary: str, score: ScoreSummary, sec_available: bool) -> VerificationResult:
    warnings = []
    checks = ["Summary generated.", "Scores generated.", "Disclaimer included."]
    text = summary.lower()
    if any(x in text for x in ["buy", "sell", "hold", "kesin", "garanti"]):
        warnings.append("Output may include direct investment advice wording.")
    if score.risk_score > 70 and "low risk" in text:
        warnings.append("High risk score conflicts with low-risk wording.")
    if not sec_available:
        checks.append("SEC data unavailable/not applicable was handled.")
    return VerificationResult(overall="pass" if not warnings else "review", warnings=warnings, checks=checks)


async def run_async(prompt: str, company: str, ticker: str) -> FinalReport:
    trace_id = gen_trace_id() if gen_trace_id else None
    trace_steps: List[TraceStep] = []

    plan = make_plan(prompt, company, ticker)
    trace_steps.append(TraceStep(step=1, name="Planner", summary=f"Created {plan.objective} plan.", details=plan.model_dump()))

    data = await collect_data(plan)
    trace_steps.append(TraceStep(step=2, name="Async Research", summary="Research data collection completed.", details={"source_count": len(data.get("sources", [])), "sec_available": bool(data.get("sec_excerpt"))}))

    findings = [fundamentals_finding(data), macro_finding(data), sec_finding(data), news_finding(data)]
    trace_steps.append(TraceStep(step=3, name="Specialist Analysts", summary="Analyst modules completed with evaluation notes."))

    score = compute_score(findings, data)
    previous = load_previous(ticker)
    memory = {"has_previous": bool(previous)}
    if previous:
        memory["investment_change"] = round(score.investment_score - float(previous.get("investment", 0)), 1)
        memory["risk_change"] = round(score.risk_score - float(previous.get("risk", 0)), 1)

    profile = data.get("profile", {}) or {}
    company_name = profile.get("name") or company

    # Optional Agents SDK writer: keeps final output concise. Fallback summary remains default if anything fails.
    summary = write_summary(company_name, ticker, score, findings, len(data.get("sources", [])))
    if sdk_enabled():
        try:
            @function_tool
            def fundamentals_tool() -> str:
                return findings[0].model_dump_json()

            @function_tool
            def macro_tool() -> str:
                return findings[1].model_dump_json()

            @function_tool
            def sec_risk_tool() -> str:
                return findings[2].model_dump_json()

            @function_tool
            def news_tool() -> str:
                return findings[3].model_dump_json()

            writer = Agent(
                name="summary_writer",
                instructions="Write a short Turkish executive summary. Use tools if useful. Do not give buy/sell/hold advice.",
                tools=[fundamentals_tool, macro_tool, sec_risk_tool, news_tool],
            )
            input_text = f"Company={company_name}, ticker={ticker}, score={score.model_dump_json()}, prompt={prompt}"
            if trace and trace_id:
                with trace("financial_agent_clean_v2", trace_id=trace_id):
                    result = await Runner.run(writer, input_text)
            else:
                result = await Runner.run(writer, input_text)
            if result and result.final_output:
                summary = str(result.final_output)
            trace_steps.append(TraceStep(step=4, name="Writer Agent", summary="Agents SDK writer produced summary with specialist tools."))
        except Exception as exc:
            trace_steps.append(TraceStep(step=4, name="Writer Agent", summary="Fallback writer used after SDK writer failed.", details={"error": str(exc)}))
    else:
        trace_steps.append(TraceStep(step=4, name="Writer", summary="Summary writer completed."))

    verification = verify_report(summary, score, bool(data.get("sec_excerpt")))
    trace_steps.append(TraceStep(step=5, name="Verifier", summary=f"Verification result: {verification.overall}.", details=verification.model_dump()))

    report = FinalReport(
        company=company_name,
        ticker=ticker,
        executive_summary=summary,
        score=score,
        plan=plan,
        analyst_findings=findings,
        sources=data.get("sources", []),
        verification=verification,
        memory_comparison=memory,
        trace_id=trace_id,
        trace_steps=trace_steps,
        raw_data={
            "profile": data.get("profile"),
            "financials": data.get("financials"),
            "macro": data.get("macro"),
            "sec_excerpt": data.get("sec_excerpt")[:900] if data.get("sec_excerpt") else None,
        },
    )
    save_memory(ticker, score.investment_score, score.risk_score, summary)
    return report


def run_analysis(prompt: str, company: str, ticker: str, output_dir: str = "reports") -> dict:
    report = asyncio.run(run_async(prompt, company, ticker))
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    base = Path(output_dir) / ticker.replace(".", "_")
    data = report.model_dump()
    data["json_path"] = str(base) + ".json"
    data["excel_path"] = str(base) + ".xlsx"
    export_json(data, data["json_path"])
    export_excel(data, data["excel_path"])
    return data

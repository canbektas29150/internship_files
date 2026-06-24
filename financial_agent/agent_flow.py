from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from research_planner import generate_research_plan
from schemas import AgentReport
from scoring import build_investment_score, build_risk_score
from tools import get_financial_snapshot, run_research_queries, sec_company_lookup
from trace_logger import TraceLogger
from writer import build_analyst_findings, build_executive_answer, build_report_summary


def save_report_memory(report: AgentReport) -> None:
    Path("logs").mkdir(exist_ok=True)
    memory_path = Path("logs/reports_memory.jsonl")
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt": report.prompt,
        "ticker": report.company.ticker,
        "investment": report.investment_score.total_score,
        "risk": report.risk_score.total_score,
        "executive_answer": report.executive_answer,
    }
    with memory_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def generate_report(prompt: str) -> AgentReport:
    trace = TraceLogger()

    with trace.step("planner", prompt):
        plan = generate_research_plan(prompt)
        trace.add(
            "planner",
            prompt,
            f"company={plan.company.name} ticker={plan.company.ticker} intent={plan.intent} queries={len(plan.queries)}",
        )

    with trace.step("finance_tool", plan.company.ticker):
        financial_snapshot = get_financial_snapshot(plan.company.ticker)
        trace.add("finance_tool", plan.company.ticker, financial_snapshot)

    with trace.step("sec_tool", plan.company.ticker):
        sec_snapshot = sec_company_lookup(plan.company.ticker)
        trace.add("sec_tool", plan.company.ticker, sec_snapshot)

    with trace.step("research_tools", " | ".join(q.query for q in plan.queries)):
        sources = run_research_queries(plan.queries, max_results_per_query=3)
        trace.add("research_tools", f"{len(plan.queries)} queries", f"{len(sources)} source items collected")

    with trace.step("score_calculator", plan.company.ticker):
        investment_score = build_investment_score(financial_snapshot, len(sources))
        risk_score = build_risk_score(financial_snapshot, len(sources), sec_snapshot.get("status", "unknown"))
        trace.add(
            "score_calculator",
            plan.company.ticker,
            f"investment={investment_score.total_score}, risk={risk_score.total_score}",
        )

    with trace.step("answer_writer", prompt):
        executive_answer = build_executive_answer(plan, investment_score, risk_score, sources)
        analyst_findings = build_analyst_findings(plan, investment_score, risk_score, sources)
        summary = build_report_summary(plan, investment_score, risk_score, sources)
        trace.add("answer_writer", prompt, executive_answer)

    verifier_notes = []
    if not sources:
        verifier_notes.append("No live web sources were collected; answer confidence is lower.")
    if financial_snapshot.get("status") != "ok":
        verifier_notes.append(f"Financial data status is {financial_snapshot.get('status')}: {financial_snapshot.get('error')}")
    if plan.company.confidence < 0.6:
        verifier_notes.append("Company/ticker resolution confidence is low; user confirmation may be needed.")
    if not verifier_notes:
        verifier_notes.append("Report generated with available data. Check source list and score breakdown before relying on conclusions.")

    trace.add("verifier", prompt, " | ".join(verifier_notes))

    report = AgentReport(
        prompt=prompt,
        company=plan.company,
        plan=plan,
        executive_answer=executive_answer,
        investment_score=investment_score,
        risk_score=risk_score,
        analyst_findings=analyst_findings,
        sources=sources,
        data_snapshot={
            "financial_snapshot": financial_snapshot,
            "sec_snapshot": sec_snapshot,
        },
        verifier_notes=verifier_notes,
        trace_events=trace.events,
    )

    save_report_memory(report)
    return report

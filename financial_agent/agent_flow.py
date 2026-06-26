from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from research_planner import generate_research_plan
from schemas import AgentReport
from scoring import build_global_evidence_map, build_investment_score, build_risk_score
from tools import get_financial_snapshot, run_research_queries_with_trace, sec_company_lookup
from trace_logger import TraceLogger
from writer import build_analyst_findings, build_executive_answer, build_report_summary, validate_final_answer


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


def _planner_reasoning(plan) -> List[str]:
    return [
        f"Company resolver returned {plan.company.name} ({plan.company.ticker}) with confidence {plan.company.confidence}.",
        f"Intent detector classified the prompt as '{plan.intent}'.",
        f"Timeframe detector returned '{plan.timeframe}'.",
        f"Research planner generated {len(plan.queries)} web/search queries.",
    ]


def _planner_validation(plan) -> Dict[str, Any]:
    return {
        "ticker_present": bool(plan.company.ticker),
        "resolver_confidence_ok": plan.company.confidence >= 0.6,
        "queries_generated": len(plan.queries) > 0,
        "questions_generated": len(plan.questions_to_answer) > 0,
    }


def _verifier_notes(plan, financial_snapshot, sec_snapshot, sources, answer_validation) -> List[str]:
    notes: List[str] = []
    if not sources:
        notes.append("No live web sources were collected; answer confidence is lower.")
    if financial_snapshot.get("status") != "ok":
        notes.append(f"Financial data status is {financial_snapshot.get('status')}: {financial_snapshot.get('error')}")
    if sec_snapshot.get("status") != "ok":
        notes.append(f"SEC lookup status is {sec_snapshot.get('status')}: {sec_snapshot.get('error')}")
    if plan.company.confidence < 0.6:
        notes.append("Company/ticker resolution confidence is low; user confirmation may be needed.")
    if answer_validation.get("unsupported_claims", 0) > 0:
        notes.append(f"Final answer has {answer_validation.get('unsupported_claims')} unsupported/weakly supported claim(s).")
    if not notes:
        notes.append("Report generated with available data. Check source list and score breakdown before relying on conclusions.")
    return notes


def generate_report(prompt: str) -> AgentReport:
    trace = TraceLogger()

    with trace.step(
        "planner",
        prompt,
        goal="Resolve company/ticker, detect intent/timeframe and generate research questions.",
        tool="research_planner.generate_research_plan",
        data_source="user_prompt + local resolver rules",
    ) as ctx:
        plan = generate_research_plan(prompt)
        ctx["output_summary"] = (
            f"company={plan.company.name} ticker={plan.company.ticker} "
            f"intent={plan.intent} timeframe={plan.timeframe} queries={len(plan.queries)}"
        )
        ctx["confidence"] = plan.company.confidence
        ctx["decision"] = {
            "company": plan.company.name,
            "ticker": plan.company.ticker,
            "intent": plan.intent,
            "timeframe": plan.timeframe,
            "resolver_reason": plan.company.reason,
        }
        ctx["reasoning"] = _planner_reasoning(plan)
        ctx["validation"] = _planner_validation(plan)
        ctx["records_returned"] = len(plan.queries)
        ctx["returned_fields"] = ["company", "ticker", "intent", "timeframe", "queries", "questions_to_answer"]
        if plan.company.confidence < 0.6:
            ctx["warnings"].append("Low company resolver confidence.")

    with trace.step(
        "finance_tool",
        plan.company.ticker,
        goal="Fetch company financial metrics and validate missing/returned fields.",
        tool="yfinance.Ticker.info",
        data_source="Yahoo Finance via yfinance",
        source_url=f"https://finance.yahoo.com/quote/{plan.company.ticker}",
    ) as ctx:
        financial_snapshot = get_financial_snapshot(plan.company.ticker)
        ctx["output_summary"] = (
            f"status={financial_snapshot.get('status')}; "
            f"returned={len(financial_snapshot.get('returned_fields', []))}; "
            f"missing={len(financial_snapshot.get('missing_fields', []))}; "
            f"error={financial_snapshot.get('error')}"
        )
        ctx["confidence"] = financial_snapshot.get("confidence", 0.0)
        ctx["requested_fields"] = financial_snapshot.get("requested_fields", [])
        ctx["returned_fields"] = financial_snapshot.get("returned_fields", [])
        ctx["missing_fields"] = financial_snapshot.get("missing_fields", [])
        ctx["records_returned"] = len(financial_snapshot.get("returned_fields", []))
        ctx["validation"] = financial_snapshot.get("validation", {})
        ctx["evidence"] = [
            {"field": k, "raw_value": v, "source": "yfinance", "source_url": financial_snapshot.get("source_url")}
            for k, v in (financial_snapshot.get("info") or {}).items()
        ]
        if financial_snapshot.get("status") != "ok":
            ctx["warnings"].append(f"Financial snapshot status: {financial_snapshot.get('status')} / {financial_snapshot.get('error')}")

    with trace.step(
        "sec_tool",
        plan.company.ticker,
        goal="Find SEC CIK to validate filing visibility for US-listed companies.",
        tool="requests.get",
        data_source="SEC company_tickers.json",
        source_url="https://www.sec.gov/files/company_tickers.json",
    ) as ctx:
        sec_snapshot = sec_company_lookup(plan.company.ticker)
        ctx["output_summary"] = f"status={sec_snapshot.get('status')}; cik={sec_snapshot.get('cik')}; error={sec_snapshot.get('error')}"
        ctx["confidence"] = sec_snapshot.get("confidence", 0.0)
        ctx["decision"] = {"ticker": plan.company.ticker, "cik": sec_snapshot.get("cik"), "status": sec_snapshot.get("status")}
        ctx["validation"] = sec_snapshot.get("validation", {})
        ctx["requested_fields"] = ["ticker", "cik_str", "title"]
        ctx["returned_fields"] = ["cik"] if sec_snapshot.get("cik") else []
        ctx["missing_fields"] = [] if sec_snapshot.get("cik") else ["cik"]
        ctx["records_returned"] = 1 if sec_snapshot.get("cik") else 0
        if sec_snapshot.get("status") != "ok":
            ctx["warnings"].append(f"SEC lookup not ok: {sec_snapshot.get('status')}")

    with trace.step(
        "research_tools",
        " | ".join(q.query for q in plan.queries),
        goal="Run web/news searches, deduplicate sources and score source quality.",
        tool="DDGS.text",
        data_source="DuckDuckGo Search via ddgs/duckduckgo_search",
        source_url="https://duckduckgo.com",
    ) as ctx:
        sources, research_trace = run_research_queries_with_trace(plan.queries, max_results_per_query=3)
        ctx["output_summary"] = (
            f"{research_trace.get('total_sources_used', 0)} source items collected from "
            f"{research_trace.get('queries_count', 0)} queries; avg_source_quality={research_trace.get('avg_source_quality')}"
        )
        ctx["records_returned"] = len(sources)
        ctx["confidence"] = min(0.95, max(0.1, (research_trace.get("avg_source_quality", 0) / 100) if sources else 0.2))
        ctx["decision"] = {
            "queries_count": research_trace.get("queries_count", 0),
            "sources_used": research_trace.get("total_sources_used", 0),
            "avg_source_quality": research_trace.get("avg_source_quality", 0),
        }
        ctx["reasoning"] = [
            f"Query '{q.get('query')}' returned {q.get('returned_results')} result(s), used {q.get('used_after_dedupe')} after dedupe."
            for q in research_trace.get("query_logs", [])[:6]
        ]
        ctx["validation"] = {
            "sources_available": len([s for s in sources if s.url]) > 0,
            "dedupe_applied": True,
            "query_logs_count": len(research_trace.get("query_logs", [])),
        }
        ctx["source_quality"] = research_trace.get("source_quality", [])
        if len([s for s in sources if s.url]) == 0:
            ctx["warnings"].append("No URL-backed web sources collected.")

    with trace.step(
        "score_calculator",
        plan.company.ticker,
        goal="Calculate investment score, risk score and metric-level evidence mapping.",
        tool="scoring.build_investment_score + scoring.build_risk_score",
        data_source="financial_snapshot + SEC status + web source count",
    ) as ctx:
        investment_score = build_investment_score(financial_snapshot, len(sources))
        risk_score = build_risk_score(financial_snapshot, len(sources), sec_snapshot.get("status", "unknown"))
        evidence_map = build_global_evidence_map(investment_score, risk_score, financial_snapshot, sec_snapshot, sources)
        ctx["output_summary"] = f"investment={investment_score.total_score}/100, risk={risk_score.total_score}/10"
        ctx["confidence"] = round((investment_score.confidence + risk_score.confidence) / 2, 3)
        ctx["decision"] = {
            "investment_score": investment_score.total_score,
            "risk_score": risk_score.total_score,
            "investment_confidence": investment_score.confidence,
            "risk_confidence": risk_score.confidence,
        }
        ctx["reasoning"] = [
            "Each score is a weighted sum of MetricScore rows.",
            "Investment Score remains 0-100.",
            "Risk Score is displayed on a 1-10 scale while raw metric scores stay 0-100 for explainability.",
        ]
        ctx["validation"] = {
            "investment_metrics_count": len(investment_score.metrics),
            "risk_metrics_count": len(risk_score.metrics),
            "risk_scale": "1-10",
            "evidence_map_created": True,
        }
        ctx["records_returned"] = len(investment_score.metrics) + len(risk_score.metrics)
        ctx["returned_fields"] = [m.name for m in investment_score.metrics + risk_score.metrics]
        ctx["evidence"] = evidence_map.get("investment_score", {}).get("metrics", []) + evidence_map.get("risk_score", {}).get("metrics", [])

    with trace.step(
        "answer_writer",
        prompt,
        goal="Generate direct answer, analyst findings and validate final answer claims.",
        tool="writer.build_executive_answer + validate_final_answer",
        data_source="Ollama if available, deterministic fallback otherwise",
    ) as ctx:
        executive_answer = build_executive_answer(plan, investment_score, risk_score, sources)
        analyst_findings = build_analyst_findings(plan, investment_score, risk_score, sources)
        summary = build_report_summary(plan, investment_score, risk_score, sources)
        answer_validation = validate_final_answer(executive_answer, plan, investment_score, risk_score, sources)
        ctx["output_summary"] = executive_answer
        ctx["confidence"] = answer_validation.get("confidence", 0.0)
        ctx["decision"] = {
            "writer_mode": "ollama_or_fallback",
            "analyst_findings_count": len(analyst_findings),
            "supported_claims": answer_validation.get("supported_claims"),
            "unsupported_claims": answer_validation.get("unsupported_claims"),
        }
        ctx["validation"] = answer_validation
        ctx["claim_checks"] = answer_validation.get("claim_checks", [])
        ctx["records_returned"] = len(analyst_findings)
        if answer_validation.get("unsupported_claims", 0) > 0:
            ctx["warnings"].append("Some final answer claims are weakly supported or unsupported.")

    verifier_notes = _verifier_notes(plan, financial_snapshot, sec_snapshot, sources, answer_validation)
    trace.add(
        "verifier",
        prompt,
        " | ".join(verifier_notes),
        goal="Check data availability, source reliability and answer support.",
        tool="verifier_rules",
        data_source="internal report checks",
        confidence=max(0.1, min(0.98, answer_validation.get("confidence", 0.0))),
        validation={
            "financial_status_ok": financial_snapshot.get("status") == "ok",
            "sec_status_ok": sec_snapshot.get("status") == "ok",
            "has_url_sources": len([s for s in sources if s.url]) > 0,
            "unsupported_claims": answer_validation.get("unsupported_claims", 0),
        },
        warnings=[n for n in verifier_notes if "not" in n.lower() or "error" in n.lower() or "unsupported" in n.lower()],
        records_returned=len(verifier_notes),
    )

    trace_report = trace.to_report()
    data_snapshot = {
        "financial_snapshot": financial_snapshot,
        "sec_snapshot": sec_snapshot,
        "research_trace": research_trace,
        "evidence_map": evidence_map,
        "answer_validation": answer_validation,
        "trace_report": trace_report,
        "report_summary": summary,
    }

    report = AgentReport(
        prompt=prompt,
        company=plan.company,
        plan=plan,
        executive_answer=executive_answer,
        investment_score=investment_score,
        risk_score=risk_score,
        analyst_findings=analyst_findings,
        sources=sources,
        data_snapshot=data_snapshot,
        verifier_notes=verifier_notes,
        trace_events=trace.events,
    )

    save_report_memory(report)
    return report

from __future__ import annotations

from dataclasses import asdict
import json
import streamlit as st

from agent_flow import generate_report


st.set_page_config(page_title="Financial Agent", layout="wide", initial_sidebar_state="collapsed")


def inject_css() -> None:
    """Keep the existing simple black/white dashboard look."""
    st.markdown(
        """
        <style>
        .stApp { background-color: #000000; color: #f5f5f5; }
        header[data-testid="stHeader"] { background-color: #000000 !important; color: #f5f5f5 !important; }
        header[data-testid="stHeader"] * { color: #f5f5f5 !important; }
        div[data-testid="stTextInput"] input {
            background-color: #111111; color: #ffffff; border: 1px solid #444444;
        }
        div[data-testid="stButton"] button {
            background-color: #111111; color: #ffffff; border: 1px solid #444444;
        }
        div[data-testid="stButton"] button:hover { background-color: #222222; }
        .block-container { max-width: 1400px; padding-top: 2rem; }
        a { color: #ffffff !important; text-decoration: underline !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _display_value(value):
    """Convert nested objects to strings so Streamlit/pyarrow can render them safely."""
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def _safe_rows(rows):
    """Normalize rows before st.dataframe to avoid pyarrow mixed-type conversion errors."""
    safe = []
    for row in rows or []:
        if isinstance(row, dict):
            safe.append({str(k): _display_value(v) for k, v in row.items()})
        else:
            safe.append({"value": _display_value(row)})
    return safe


def metric_table(scorecard):
    rows = []
    for m in scorecard.metrics:
        rows.append({
            "Metric": m.name,
            "Value": m.value,
            "Score": m.score,
            "Weight": m.weight,
            "Weighted": round(m.score * m.weight, 2),
            "Source": m.source,
            "Source URL": getattr(m, "source_url", ""),
            "Explanation": m.explanation,
            "Validation": getattr(m, "validation", {}),
        })
    try:
        st.dataframe(
            _safe_rows(rows),
            use_container_width=True,
            hide_index=True,
            column_config={"Source URL": st.column_config.LinkColumn("Source URL")},
        )
    except Exception:
        st.dataframe(_safe_rows(rows), use_container_width=True, hide_index=True)


def sources_table(sources):
    if not sources:
        st.info("Canlı kaynak bulunamadı veya arama aracı çalışmadı.")
        return
    for idx, s in enumerate(sources, start=1):
        title = s.title or "Untitled Source"
        link = f"[{title}]({s.url})" if s.url else title
        st.markdown(f"**{idx}. {link}**")
        if s.source_type:
            st.caption(s.source_type)
        if s.snippet:
            st.write(s.snippet)
        st.markdown("---")


def _event_rows(report):
    rows = []
    for e in report.trace_events:
        rows.append({
            "Step": e.step,
            "Status": e.status,
            "Latency (ms)": e.latency_ms,
            "Confidence": e.confidence,
            "Goal": e.goal,
            "Tool": e.tool,
            "Data Source": e.data_source,
            "Source URL": e.source_url,
            "Records": e.records_returned,
            "Input": e.input_summary,
            "Output": e.output_summary,
            "Warnings": "; ".join(e.warnings),
        })
    return rows


def trace_timeline(report):
    rows = _event_rows(report)
    if not rows:
        st.info("Trace kaydı yok.")
        return
    try:
        st.dataframe(
            _safe_rows(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Source URL": st.column_config.LinkColumn("Source URL"),
                "Goal": st.column_config.TextColumn("Goal", width="large"),
                "Input": st.column_config.TextColumn("Input", width="large"),
                "Output": st.column_config.TextColumn("Output", width="large"),
                "Warnings": st.column_config.TextColumn("Warnings", width="large"),
            },
        )
    except Exception:
        st.dataframe(_safe_rows(rows), use_container_width=True, hide_index=True)


def trace_decision_log(report):
    rows = []
    for e in report.trace_events:
        if e.decision or e.reasoning or e.validation:
            rows.append({
                "Step": e.step,
                "Decision": e.decision,
                "Reasoning": " | ".join(e.reasoning),
                "Validation": e.validation,
                "Confidence": e.confidence,
            })
    st.dataframe(_safe_rows(rows), use_container_width=True, hide_index=True) if rows else st.info("Decision log yok.")


def trace_tool_calls(report):
    rows = []
    for e in report.trace_events:
        if e.tool:
            rows.append({
                "Step": e.step,
                "Tool": e.tool,
                "Data Source": e.data_source,
                "Source URL": e.source_url,
                "Requested Fields": ", ".join(e.requested_fields),
                "Returned Fields": ", ".join(e.returned_fields),
                "Missing Fields": ", ".join(e.missing_fields),
                "Records": e.records_returned,
                "Latency (ms)": e.latency_ms,
                "Status": e.status,
            })
    if rows:
        try:
            st.dataframe(
                _safe_rows(rows),
                use_container_width=True,
                hide_index=True,
                column_config={"Source URL": st.column_config.LinkColumn("Source URL")},
            )
        except Exception:
            st.dataframe(_safe_rows(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Tool call trace yok.")


def trace_evidence_mapping(report):
    evidence_map = report.data_snapshot.get("evidence_map", {})
    if not evidence_map:
        st.info("Evidence mapping bulunamadı.")
        return

    inv_rows = evidence_map.get("investment_score", {}).get("metrics", [])
    risk_rows = evidence_map.get("risk_score", {}).get("metrics", [])

    st.markdown("#### Investment Evidence Mapping")
    st.dataframe(_safe_rows(inv_rows), use_container_width=True, hide_index=True)
    st.markdown("#### Risk Evidence Mapping")
    st.dataframe(_safe_rows(risk_rows), use_container_width=True, hide_index=True)


def trace_source_quality(report):
    research_trace = report.data_snapshot.get("research_trace", {})
    rows = research_trace.get("source_quality", [])
    if rows:
        try:
            st.dataframe(
                _safe_rows(rows),
                use_container_width=True,
                hide_index=True,
                column_config={"url": st.column_config.LinkColumn("url")},
            )
        except Exception:
            st.dataframe(_safe_rows(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Kaynak kalite raporu yok veya canlı kaynak alınamadı.")

    with st.expander("Search Query Logs", expanded=False):
        st.dataframe(_safe_rows(research_trace.get("query_logs", [])), use_container_width=True, hide_index=True)


def trace_validation(report):
    answer_validation = report.data_snapshot.get("answer_validation", {})
    claim_checks = answer_validation.get("claim_checks", [])
    col1, col2, col3 = st.columns(3)
    col1.metric("Supported Claims", answer_validation.get("supported_claims", 0))
    col2.metric("Unsupported Claims", answer_validation.get("unsupported_claims", 0))
    col3.metric("Answer Confidence", answer_validation.get("confidence", 0))
    if claim_checks:
        st.dataframe(_safe_rows(claim_checks), use_container_width=True, hide_index=True)
    else:
        st.info("Claim validation kaydı yok.")


def trace_downloads(report):
    trace_json = json.dumps([asdict(e) for e in report.trace_events], ensure_ascii=False, indent=2)
    raw_json = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Trace JSON indir",
            data=trace_json,
            file_name=f"{report.company.ticker}_trace.json",
            mime="application/json",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            "Raw Report JSON indir",
            data=raw_json,
            file_name=f"{report.company.ticker}_raw_report.json",
            mime="application/json",
            use_container_width=True,
        )


def main():
    inject_css()
    st.title("Financial Agent")
    st.caption("Promptu okur, şirketi çözer, araştırma planı üretir, araçları çağırır, skorlar ve trace timeline gösterir.")
    st.caption(
        "Veri kaynakları: yfinance finansal veriler, DuckDuckGo web araması, SEC CIK listesi ve Ollama modeli. "
        "Analiz adımları ve kaynaklar `logs/trace_events.jsonl` dosyasına kaydedilir."
    )

    prompt = st.text_input("Analiz promptu", value="Apple 3. çeyrekte nasıl bir şey yapar")
    run = st.button("Analiz Et")

    if not run:
        st.stop()

    try:
        with st.spinner("Agent araştırıyor..."):
            report = generate_report(prompt)
    except Exception as exc:
        st.error(f"Hata: {exc}")
        st.exception(exc)
        st.stop()

    st.subheader("Ön Cevap")
    st.write(report.executive_answer)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Company", f"{report.company.name}", report.company.ticker)
    with col2:
        st.metric("Investment Score", f"{report.investment_score.total_score}/100")
    with col3:
        st.metric("Risk Score", f"{report.risk_score.total_score}/10")

    tabs = st.tabs([
        "Research Plan",
        "Score Breakdown",
        "Analyst Findings",
        "Sources",
        "Data Snapshot",
        "Trace Timeline",
        "Raw JSON",
    ])

    with tabs[0]:
        st.markdown("### Planner Output")
        st.write(f"**Intent:** {report.plan.intent}")
        st.write(f"**Timeframe:** {report.plan.timeframe}")
        st.write(f"**Resolver confidence:** {report.company.confidence} — {report.company.reason}")

        st.markdown("### Questions to Answer")
        for q in report.plan.questions_to_answer:
            st.write(f"- {q}")

        st.markdown("### Generated Research Queries")
        st.dataframe(_safe_rows([asdict(q) for q in report.plan.queries]), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.markdown("### Investment Score Breakdown")
        st.caption(f"Score confidence: {report.investment_score.confidence}")
        metric_table(report.investment_score)
        st.markdown("### Risk Score Breakdown (1–10 scale)")
        st.caption(f"Score confidence: {report.risk_score.confidence}")
        metric_table(report.risk_score)

    with tabs[2]:
        for finding in report.analyst_findings:
            with st.expander(finding.role, expanded=True):
                st.write(finding.assessment)
                st.markdown("**Positive / Useful signals**")
                for x in finding.positives:
                    st.write(f"- {x}")
                st.markdown("**Risks / Limits**")
                for x in finding.risks:
                    st.write(f"- {x}")

        st.markdown("### Verifier Notes")
        for note in report.verifier_notes:
            st.write(f"- {note}")

    with tabs[3]:
        sources_table(report.sources)

    with tabs[4]:
        st.json(report.data_snapshot)

    with tabs[5]:
        st.markdown("### Trace Timeline")
        st.caption("Bu bölüm agent'ın hangi adımda neyi nereden aldığını, hangi alanları eksik bıraktığını ve çıktının ne kadar destekli olduğunu gösterir.")
        trace_timeline(report)

        with st.expander("Decision Log", expanded=False):
            trace_decision_log(report)
        with st.expander("Tool Calls / Field Coverage", expanded=False):
            trace_tool_calls(report)
        with st.expander("Evidence Mapping", expanded=False):
            trace_evidence_mapping(report)
        with st.expander("Source Quality", expanded=False):
            trace_source_quality(report)
        with st.expander("Final Answer Validation", expanded=False):
            trace_validation(report)
        with st.expander("Downloads", expanded=False):
            trace_downloads(report)

        st.caption("Aynı kayıtlar logs/trace_events.jsonl içine de yazılır.")

    with tabs[6]:
        st.json(report.to_dict())


if __name__ == "__main__":
    main()

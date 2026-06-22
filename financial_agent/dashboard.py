from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import streamlit as st

from agent_flow import run_analysis
from resolver import resolve_candidates


APP_TITLE = "Financial Research Agent"
APP_SUBTITLE = "Structured company research, analyst review and verification"


def init_state() -> None:
    if "results" not in st.session_state:
        st.session_state.results = []
    if "pending_confirmation" not in st.session_state:
        st.session_state.pending_confirmation = None
    if "output_dir" not in st.session_state:
        st.session_state.output_dir = "reports"


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #000000;
            --panel: #070707;
            --panel2: #0D0D0D;
            --line: #2A2A2A;
            --line2: #1A1A1A;
            --text: #FFFFFF;
            --muted: #BDBDBD;
            --muted2: #808080;
        }

        html, body, .stApp, [data-testid="stAppViewContainer"] {
            background: var(--bg) !important;
            color: var(--text) !important;
            font-family: Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        #MainMenu,
        footer,
        header {
            visibility: hidden !important;
            display: none !important;
            height: 0 !important;
        }

        .block-container {
            padding-top: 1.4rem !important;
            max-width: 1180px !important;
        }

        .app-header {
            border: 1px solid var(--line);
            background: var(--panel);
            border-radius: 18px;
            padding: 1.25rem 1.35rem;
            margin-bottom: 1.1rem;
        }

        .app-title {
            font-size: 2rem;
            line-height: 1.15;
            font-weight: 760;
            letter-spacing: -0.035em;
        }

        .app-subtitle {
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.96rem;
        }

        .panel {
            border: 1px solid var(--line);
            background: var(--panel);
            border-radius: 16px;
            padding: 1rem 1.05rem;
            margin: 0.75rem 0;
        }

        .thin-panel {
            border: 1px solid var(--line2);
            background: var(--panel2);
            border-radius: 14px;
            padding: 0.85rem 0.95rem;
            margin: 0.55rem 0;
        }

        .label {
            color: var(--muted2);
            text-transform: uppercase;
            letter-spacing: .07em;
            font-size: .68rem;
            font-weight: 700;
            margin-bottom: .2rem;
        }

        .muted {
            color: var(--muted);
        }

        .error-panel {
            border: 1px solid var(--line);
            background: var(--panel);
            border-radius: 14px;
            padding: 1rem;
            margin-top: .8rem;
        }

        .source-card {
            border: 1px solid var(--line);
            background: var(--panel);
            border-radius: 14px;
            padding: .9rem 1rem;
            margin-bottom: .75rem;
        }

        .stMetric {
            background: var(--panel) !important;
            border: 1px solid var(--line) !important;
            border-radius: 16px !important;
            padding: 1rem !important;
        }

        div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] {
            color: var(--text) !important;
        }

        div[data-testid="stMetricLabel"] {
            color: var(--muted) !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            border-bottom: 1px solid var(--line);
            gap: .35rem;
        }

        .stTabs [data-baseweb="tab"] {
            color: var(--muted);
            background: transparent !important;
            border-radius: 10px 10px 0 0;
            font-weight: 650;
        }

        .stTabs [aria-selected="true"] {
            color: var(--text) !important;
            border-bottom: 2px solid var(--text) !important;
            background: rgba(255,255,255,0.06) !important;
        }

        .stTextInput input, [data-testid="stChatInput"] textarea {
            background: var(--panel) !important;
            color: var(--text) !important;
            border: 1px solid var(--line) !important;
            border-radius: 12px !important;
        }

        .stButton > button, .stDownloadButton > button {
            background: var(--panel2) !important;
            color: var(--text) !important;
            border: 1px solid var(--line) !important;
            border-radius: 12px !important;
            font-weight: 650 !important;
        }

        .stButton > button:hover, .stDownloadButton > button:hover {
            background: #171717 !important;
            border-color: #FFFFFF !important;
            color: #FFFFFF !important;
        }

        h1, h2, h3, h4, p, li, span, div {
            font-family: Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
        }

        a {
            color: #FFFFFF !important;
            text-decoration: underline;
        }

        code {
            background: #111111 !important;
            color: #FFFFFF !important;
            border: 1px solid var(--line);
            border-radius: 6px;
            padding: .1rem .3rem;
        }

        hr {
            border-color: var(--line) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def fmt(value: Any) -> str:
    if value is None or value == "":
        return "Not available"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def header() -> None:
    st.markdown(
        f"""
        <div class="app-header">
            <div class="app-title">{APP_TITLE}</div>
            <div class="app-subtitle">{APP_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def search_panel() -> None:
    with st.form("research_form", clear_on_submit=False):
        col1, col2 = st.columns([5, 1])
        with col1:
            query = st.text_input(
                "Company or ticker",
                placeholder="Apple, AAPL, Ford, ASELS.IS, Ethereum...",
                label_visibility="collapsed",
            )
        with col2:
            submitted = st.form_submit_button("Research", use_container_width=True)

    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("Clear", use_container_width=True):
            st.session_state.results = []
            st.session_state.pending_confirmation = None
            st.rerun()

    if submitted and query.strip():
        candidates = resolve_candidates(query.strip())

        if not candidates:
            st.session_state.pending_confirmation = None
            st.session_state.results.insert(0, {
                "error": "No match found. Try a clearer company name or ticker.",
                "query": query.strip(),
            })
            st.rerun()

        if len(candidates) == 1 and candidates[0].source in {"ticker_exact", "ticker_raw"}:
            with st.spinner("Researching..."):
                result = run_analysis(query.strip(), candidates[0].label, candidates[0].ticker, st.session_state.output_dir)
            result["query"] = query.strip()
            st.session_state.results.insert(0, result)
            st.session_state.pending_confirmation = None
            st.rerun()

        st.session_state.pending_confirmation = {
            "query": query.strip(),
            "candidates": [c.model_dump() for c in candidates],
        }
        st.rerun()


def show_confirmation() -> None:
    pending = st.session_state.pending_confirmation
    if not pending:
        return

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### Select the matching asset")
    st.caption("The query matches one or more known assets. Choose one to continue.")

    for i, c in enumerate(pending["candidates"]):
        with st.container(border=True):
            st.markdown(f"**{c['label']}**")
            st.caption(f"Ticker: {c['ticker']} · Country/Type: {c.get('country') or 'N/A'} · Confidence: {c.get('confidence'):.2f}")
            if st.button("Select", key=f"select_{i}", use_container_width=True):
                with st.spinner("Researching..."):
                    result = run_analysis(pending["query"], c["label"], c["ticker"], st.session_state.output_dir)
                result["query"] = pending["query"]
                st.session_state.results.insert(0, result)
                st.session_state.pending_confirmation = None
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def show_error(result: dict) -> None:
    st.markdown('<div class="error-panel">', unsafe_allow_html=True)
    st.markdown("### No result")
    st.write(result.get("error", "The request could not be processed."))
    st.caption(f"Query: {result.get('query', '-')}")
    st.markdown("</div>", unsafe_allow_html=True)


def show_score_cards(score: Dict[str, Any]) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Investment Score", f"{score.get('investment_score', 0)}/100")
    c2.metric("Risk Score", f"{score.get('risk_score', 0)}/100")
    c3.metric("Risk Level", score.get("risk_level", "N/A"))


def show_overview(result: dict) -> None:
    raw = result.get("raw_data", {})
    profile = raw.get("profile") or {}

    c1, c2, c3, c4 = st.columns(4)
    for col, label, value in [
        (c1, "Company", result.get("company")),
        (c2, "Ticker", result.get("ticker")),
        (c3, "Sector", profile.get("sector")),
        (c4, "Country / Type", profile.get("country")),
    ]:
        col.markdown(f'<div class="label">{label}</div>', unsafe_allow_html=True)
        col.markdown(f"**{fmt(value)}**")


def show_bullets(title: str, items: list[str]) -> None:
    st.markdown(f"#### {title}")
    if not items:
        st.caption("No clear signal was detected.")
        return
    for item in items:
        st.markdown(f"- {item}")


def analyst_role(name: str) -> str:
    n = (name or "").lower()
    if "fundamentals" in n:
        return "Reviews growth, margin, cash flow and valuation metrics."
    if "macro" in n:
        return "Reviews interest rate, inflation and GDP growth context."
    if "sec" in n:
        return "Checks SEC EDGAR filing availability and risk factor text."
    if "news" in n:
        return "Reviews recent sources for positive signals and event risk."
    return "Reviews one part of the research workflow."


def show_analysts(findings: list[dict]) -> None:
    if not findings:
        st.caption("No analyst finding was generated.")
        return

    for f in findings:
        st.markdown('<div class="thin-panel">', unsafe_allow_html=True)
        name = f.get("name", "Analyst")
        st.markdown(f"### {name}")
        st.caption(analyst_role(name))
        st.write(f.get("summary", ""))

        left, right = st.columns(2)
        with left:
            show_bullets("Positive Signals", f.get("positives", []))
        with right:
            show_bullets("Risk / Limitation Signals", f.get("risks", []))
        st.markdown("</div>", unsafe_allow_html=True)


def show_sources(sources: list[dict]) -> None:
    if not sources:
        st.caption("No relevant source was retrieved.")
        return

    for i, s in enumerate(sources, 1):
        st.markdown('<div class="source-card">', unsafe_allow_html=True)
        st.markdown(f"**{i}. {s.get('title') or 'Untitled source'}**")
        if s.get("summary"):
            st.write(s["summary"])
        if s.get("url"):
            st.markdown(f"[Open source]({s['url']})")
        st.caption(f"Query: {s.get('query', '-')}")
        st.markdown("</div>", unsafe_allow_html=True)


def show_verification(v: Dict[str, Any]) -> None:
    st.markdown(f"**Overall:** {v.get('overall', 'unknown')}")
    warnings = v.get("warnings", [])
    checks = v.get("checks", [])

    if warnings:
        st.markdown("#### Warnings")
        for w in warnings:
            st.markdown(f"- {w}")
    else:
        st.caption("No major warning was detected.")

    if checks:
        st.markdown("#### Checks")
        for c in checks:
            st.markdown(f"- {c}")


def show_data_trace(result: dict) -> None:
    raw = result.get("raw_data", {})
    profile = raw.get("profile") or {}
    financials = raw.get("financials") or {}
    macro = raw.get("macro") or {}
    factors = macro.get("factors") or {}

    st.markdown("### Data Snapshot")
    c1, c2, c3 = st.columns(3)
    c1.write(f"Market cap: **{fmt(profile.get('market_cap'))}**")
    c2.write(f"Revenue growth: **{fmt(financials.get('revenue_growth'))}**")
    c3.write(f"P/E ratio: **{fmt(financials.get('pe_ratio'))}**")

    c4, c5, c6 = st.columns(3)
    c4.write(f"Macro score: **{fmt(macro.get('score'))}/100**")
    c5.write(f"Inflation: **{fmt(factors.get('inflation'))}**")
    c6.write(f"GDP growth: **{fmt(factors.get('gdp_growth'))}**")

    st.markdown("### Trace Timeline")
    if result.get("trace_id"):
        st.caption(f"Trace ID: {result['trace_id']}")
    for step in result.get("trace_steps", []):
        st.markdown(f"**{step.get('step')}. {step.get('name')}**")
        st.caption(step.get("summary", ""))

    st.markdown("### Previous Analysis")
    memory = result.get("memory_comparison", {})
    if not memory.get("has_previous"):
        st.caption("No prior analysis is available for this ticker.")
    else:
        st.write(f"Investment score change: **{memory.get('investment_change')}**")
        st.write(f"Risk score change: **{memory.get('risk_change')}**")


def show_plan(plan: Dict[str, Any]) -> None:
    st.write("The planner converts the request into a focused research workflow.")
    st.markdown("#### Objective")
    st.write(plan.get("objective", "Not available"))

    st.markdown("#### Focus Areas")
    st.write(", ".join(plan.get("focus_areas", [])) or "Not available")

    st.markdown("#### Research Queries")
    for q in plan.get("queries", []):
        st.markdown(f"- `{q}`")

    st.markdown("#### Tools")
    st.write(", ".join(plan.get("tools", [])) or "Not available")


def show_result(result: dict) -> None:
    if result.get("error"):
        show_error(result)
        return

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    show_overview(result)
    st.markdown("</div>", unsafe_allow_html=True)

    show_score_cards(result.get("score", {}))

    st.markdown("## Executive Summary")
    st.markdown(result.get("executive_summary", "No summary generated."))

    left, right = st.columns(2)
    with left:
        show_bullets("Key Positives", result.get("score", {}).get("positives", []))
    with right:
        show_bullets("Key Risks", result.get("score", {}).get("risks", []))

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Analysts", "Sources", "Verification", "Data & Trace", "Research Plan"])

    with tab1:
        show_analysts(result.get("analyst_findings", []))
    with tab2:
        show_sources(result.get("sources", []))
    with tab3:
        show_verification(result.get("verification", {}))
    with tab4:
        show_data_trace(result)
    with tab5:
        show_plan(result.get("plan", {}))

    d1, d2 = st.columns(2)
    if result.get("json_path") and Path(result["json_path"]).exists():
        d1.download_button("Download JSON", Path(result["json_path"]).read_bytes(), file_name=Path(result["json_path"]).name)
    if result.get("excel_path") and Path(result["excel_path"]).exists():
        d2.download_button("Download Excel", Path(result["excel_path"]).read_bytes(), file_name=Path(result["excel_path"]).name)


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get Help": None, "Report a bug": None, "About": None},
    )
    init_state()
    inject_css()
    header()
    search_panel()
    show_confirmation()

    for result in st.session_state.results:
        show_result(result)


if __name__ == "__main__":
    main()

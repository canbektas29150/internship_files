from __future__ import annotations

from dataclasses import asdict
import json
import streamlit as st

from agent_flow import generate_report


st.set_page_config(page_title="Financial Agent", layout="wide", initial_sidebar_state="collapsed")


def inject_css() -> None:
    """
    Inject a simple black–white theme for the dashboard.

    The original version attempted to implement a dark theme and hacked into
    Streamlit's header styles via CSS. Users found the grey header and
    inconsistent colours distracting. This version applies a consistent
    black background with light text across the entire app—including
    buttons and input fields—while leaving the default Streamlit layout
    otherwise untouched. Keeping the CSS simple makes it easier to tweak
    later without breaking Streamlit updates.
    """
    st.markdown(
        """
        <style>
        /* Overall app background and text */
        .stApp {
            background-color: #000000;
            color: #f5f5f5;
        }

        /* Header bar */
        header[data-testid="stHeader"] {
            background-color: #000000 !important;
            color: #f5f5f5 !important;
        }
        header[data-testid="stHeader"] * {
            color: #f5f5f5 !important;
        }

        /* Input boxes */
        div[data-testid="stTextInput"] input {
            background-color: #111111;
            color: #ffffff;
            border: 1px solid #444444;
        }

        /* Buttons */
        div[data-testid="stButton"] button {
            background-color: #111111;
            color: #ffffff;
            border: 1px solid #444444;
        }
        div[data-testid="stButton"] button:hover {
            background-color: #222222;
        }

        /* Constrain the main content width for readability */
        .block-container {
            max-width: 1400px;
            padding-top: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
            "Explanation": m.explanation,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


def sources_table(sources):
    """
    Render the list of collected sources as a set of clickable entries.

    Rather than dumping a bare dataframe, this function prints each source
    with a markdown link and its snippet. This makes it obvious what the
    source is and allows users to open the link directly from the app.
    If no sources are available (for example when the search tool is
    unavailable), a friendly message is shown instead.
    """
    if not sources:
        st.info("Canlı kaynak bulunamadı veya arama aracı çalışmadı.")
        return
    for idx, s in enumerate(sources, start=1):
        # Only include a link if we have a URL; otherwise show the title
        title = s.title or "Untitled Source"
        link = f"[{title}]({s.url})" if s.url else title
        st.markdown(f"**{idx}. {link}**", unsafe_allow_html=True)
        if s.source_type:
            st.caption(s.source_type)
        if s.snippet:
            st.write(s.snippet)
        st.markdown("---")


def main():
    inject_css()
    st.title("Financial Agent")
    st.caption(
        "Promptu okur, şirketi çözer, araştırma planı üretir, araçları çağırır, skorlar ve trace timeline gösterir."
    )

    # Keep a minimal reference to data sources without cluttering the top of the page.
    # Users found the previous “Step & Data Tracking” or similar sections distracting
    # because they provided little value. A concise note is therefore displayed
    # above the prompt field instead of in a separate expander.
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
        # Risk score is now reported on a 1–10 scale
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
        st.dataframe([asdict(q) for q in report.plan.queries], use_container_width=True, hide_index=True)

    with tabs[1]:
        st.markdown("### Investment Score Breakdown")
        metric_table(report.investment_score)
        st.markdown("### Risk Score Breakdown (1–10 scale)")
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
        st.dataframe([asdict(e) for e in report.trace_events], use_container_width=True, hide_index=True)
        st.caption("Aynı kayıtlar logs/trace_events.jsonl içine de yazılır.")

    with tabs[6]:
        st.json(report.to_dict())


if __name__ == "__main__":
    main()

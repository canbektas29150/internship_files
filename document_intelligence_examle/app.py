"""Streamlit dashboard for the document intelligence pipeline."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from exporters import save_excel, save_json
from minimax_client import MiniMaxM3Client, OllamaConfig
from pipeline import DocumentIntelligencePipeline


st.set_page_config(page_title="Document Intelligence - MiniMax M3", layout="wide")
st.title("Document Intelligence with Ollama Cloud MiniMax M3")
st.caption("OpenAI API kullanmaz. Ollama native /api/chat endpoint'i üzerinden çalışır.")

with st.sidebar:
    st.header("Model Settings")
    use_direct = st.toggle("Direct Ollama Cloud API", value=False)
    host = st.text_input("OLLAMA_HOST", value="https://ollama.com" if use_direct else "http://localhost:11434")
    model = st.text_input("OLLAMA_MODEL", value="minimax-m3:cloud")
    api_key = st.text_input("OLLAMA_API_KEY", type="password", value="")
    timeout = st.number_input("Timeout seconds", min_value=30, max_value=600, value=120, step=30)

uploaded = st.file_uploader("Upload TXT, PDF, PNG, JPG, WEBP, or TIFF", type=["txt", "md", "pdf", "png", "jpg", "jpeg", "webp", "tif", "tiff"])

if uploaded is not None:
    suffix = Path(uploaded.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        temp_path = Path(tmp.name)

    st.info(f"Loaded file: {uploaded.name}")

    if st.button("Analyze Document", type="primary"):
        with st.spinner("Running extraction and verification..."):
            config = OllamaConfig(host=host, model=model, api_key=api_key or None, timeout=int(timeout))
            client = MiniMaxM3Client(config)
            pipeline = DocumentIntelligencePipeline(client)
            result = pipeline.analyze_file(temp_path)

            out_dir = Path("outputs")
            json_path = save_json(result, out_dir, "dashboard_analysis.json")
            excel_path = save_excel(result, out_dir, "dashboard_analysis.xlsx")

        analysis = result["analysis"]
        verification = result["verification"]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Document Type", analysis.get("document_type", "unknown"))
        col2.metric("Confidence", analysis.get("confidence", 0))
        col3.metric("Verification", verification.get("verification_score", 0))
        col4.metric("Human Review", str(verification.get("needs_human_review", True)))

        st.subheader("Summary")
        st.write(analysis.get("summary"))

        tab1, tab2, tab3, tab4 = st.tabs(["Fields", "Risks", "Verification", "Raw JSON"])
        with tab1:
            st.json({
                "company_name": analysis.get("company_name"),
                "document_number": analysis.get("document_number"),
                "document_date": analysis.get("document_date"),
                "due_date": analysis.get("due_date"),
                "tax_number": analysis.get("tax_number"),
                "total_amount": analysis.get("total_amount"),
                "parties": analysis.get("parties"),
            })
        with tab2:
            st.write(analysis.get("risky_clauses", []))
            st.write("Recommended actions:")
            st.write(analysis.get("recommended_actions", []))
        with tab3:
            st.json(verification)
        with tab4:
            st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")

        with open(json_path, "rb") as f:
            st.download_button("Download JSON", f, file_name="document_analysis.json")
        with open(excel_path, "rb") as f:
            st.download_button("Download Excel", f, file_name="document_analysis.xlsx")

"""
Streamlit dashboard for a minimal RAG evaluation demo.

Run:
    streamlit run app.py

The dashboard shows:
- document chunks
- retrieved chunks
- generated answer through Ollama or heuristic fallback
- RAG evaluation scores
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

import pandas as pd
import streamlit as st

from evaluation import evaluate_rag_response
from ollama_client import get_ollama_settings
from rag_engine import generate_answer, load_text_file, retrieve, split_into_chunks


ROOT_DIR = Path(__file__).resolve().parent
DOCUMENT_PATH = ROOT_DIR / "sample_docs" / "legal_contract.txt"
QUESTIONS_PATH = ROOT_DIR / "data" / "eval_questions.json"


st.set_page_config(page_title="RAG Evaluation Demo", page_icon="📄", layout="wide")


@st.cache_data
def load_demo_data() -> tuple[str, list, list]:
    document_text = load_text_file(DOCUMENT_PATH)
    chunks = split_into_chunks(document_text)
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    return document_text, chunks, questions


def run_single_question(question: str, gold_chunk_ids: list[str], top_k: int, chunks: list, answer_mode: str):
    retrieved_chunks = retrieve(question, chunks, top_k=top_k)
    answer = generate_answer(question, retrieved_chunks, answer_mode=answer_mode)
    evaluation = evaluate_rag_response(question, answer, retrieved_chunks, gold_chunk_ids)
    return answer, retrieved_chunks, evaluation


def metric_card(label: str, value: float, help_text: str) -> None:
    st.metric(label=label, value=f"{value:.3f}", help=help_text)


def main() -> None:
    _, chunks, questions = load_demo_data()
    base_url, model = get_ollama_settings()

    st.title("RAG Evaluation Demo")
    st.caption(
        "Bu demo, RAG sisteminde retrieval ve answer generation kalitesinin nasıl ölçülebileceğini gösterir. "
        "Default cevap üretimi Ollama native API üzerinden yapılır; OpenAI API kullanılmaz."
    )

    with st.sidebar:
        st.header("Ayarlar")
        st.write("**Ollama base URL:**", base_url)
        st.write("**Ollama model:**", model)

        answer_mode = st.radio(
            "Answer generation mode",
            options=["ollama", "heuristic"],
            index=0,
            help="ollama: Minimax M3/Ollama ile cevap üretir. heuristic: LLM kullanmadan basit sentence seçer.",
        )
        top_k = st.slider("Retriever kaç chunk getirsin?", min_value=1, max_value=5, value=3)
        selected_question = st.selectbox(
            "Hazır evaluation sorusu seç",
            options=[item["question"] for item in questions],
        )
        selected_item = next(item for item in questions if item["question"] == selected_question)
        question = st.text_area("Soru", value=selected_question, height=100)

        gold_input = st.text_input(
            "Gold relevant chunk ID'leri",
            value=", ".join(selected_item["gold_chunk_ids"]),
            help="Örnek: C4 veya C3, C5",
        )
        gold_chunk_ids = [item.strip() for item in gold_input.split(",") if item.strip()]

    tab_single, tab_dataset, tab_chunks = st.tabs([
        "Tek soru evaluation",
        "Dataset evaluation",
        "Document chunks",
    ])

    with tab_single:
        try:
            answer, retrieved_chunks, evaluation = run_single_question(question, gold_chunk_ids, top_k, chunks, answer_mode)
        except RuntimeError as exc:
            st.error("Ollama çağrısı başarısız oldu.")
            st.code(str(exc))
            st.markdown(
                "Kontrol et: `ollama serve` çalışıyor mu, `.env` içindeki `OLLAMA_MODEL` doğru mu? "
                "Sadece mantığı test etmek için soldan `heuristic` modunu seçebilirsin."
            )
            return

        st.subheader("Generated answer")
        st.info(answer)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            metric_card(
                "Context Precision",
                evaluation.context_precision,
                "Getirilen chunk'ların ne kadarı gerçekten relevant?",
            )
        with col2:
            metric_card(
                "Context Recall",
                evaluation.context_recall,
                "Gold relevant chunk'ların ne kadarı bulundu?",
            )
        with col3:
            metric_card(
                "Faithfulness",
                evaluation.faithfulness,
                "Cevap, getirilen context'teki bilgilere dayanıyor mu?",
            )
        with col4:
            metric_card(
                "Answer Relevancy",
                evaluation.answer_relevancy,
                "Cevap soru ile ne kadar ilişkili?",
            )

        st.write("**Evaluation note:**", evaluation.notes)

        st.subheader("Retrieved chunks")
        for chunk in retrieved_chunks:
            with st.expander(f"{chunk.chunk_id} | score={chunk.score:.3f}"):
                st.write(chunk.text)

    with tab_dataset:
        rows = []
        dataset_error = None

        for item in questions:
            try:
                answer, retrieved_chunks, evaluation = run_single_question(
                    item["question"],
                    item["gold_chunk_ids"],
                    top_k,
                    chunks,
                    answer_mode,
                )
            except RuntimeError as exc:
                dataset_error = exc
                break

            rows.append(
                {
                    "question": item["question"],
                    "gold_chunks": ", ".join(item["gold_chunk_ids"]),
                    "retrieved_chunks": ", ".join(evaluation.retrieved_chunk_ids),
                    "context_precision": evaluation.context_precision,
                    "context_recall": evaluation.context_recall,
                    "faithfulness": evaluation.faithfulness,
                    "answer_relevancy": evaluation.answer_relevancy,
                    "answer": answer,
                    "notes": evaluation.notes,
                }
            )

        if dataset_error:
            st.error("Dataset evaluation sırasında Ollama çağrısı başarısız oldu.")
            st.code(str(dataset_error))
            return

        df = pd.DataFrame(rows)

        avg_col1, avg_col2, avg_col3, avg_col4 = st.columns(4)
        with avg_col1:
            metric_card("Avg Precision", mean(df["context_precision"]), "Ortalama context precision")
        with avg_col2:
            metric_card("Avg Recall", mean(df["context_recall"]), "Ortalama context recall")
        with avg_col3:
            metric_card("Avg Faithfulness", mean(df["faithfulness"]), "Ortalama faithfulness")
        with avg_col4:
            metric_card("Avg Relevancy", mean(df["answer_relevancy"]), "Ortalama answer relevancy")

        st.dataframe(df, use_container_width=True)

    with tab_chunks:
        for chunk in chunks:
            with st.expander(chunk.chunk_id):
                st.write(chunk.text)


if __name__ == "__main__":
    main()

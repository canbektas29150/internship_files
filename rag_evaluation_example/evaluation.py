"""
RAG evaluation utilities.

The metrics here are deliberately simple and readable. They demonstrate the
main idea behind RAG evaluation:

1. Did retrieval bring the correct chunks?
2. Did generation stay faithful to the retrieved context?
3. Is the final answer relevant to the user's question?

For a production system, you can replace the heuristic faithfulness and answer
relevancy metrics with an LLM judge or a library such as Ragas/LangSmith.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Set

from rag_engine import RetrievedChunk, tokenize


@dataclass
class EvaluationResult:
    """Evaluation scores for a single RAG response."""

    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float
    retrieved_chunk_ids: List[str]
    gold_chunk_ids: List[str]
    notes: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def context_precision(retrieved_ids: Iterable[str], gold_ids: Iterable[str]) -> float:
    """
    Of the retrieved chunks, how many are actually relevant?

    Example:
    retrieved = C2, C4, C5
    gold = C2, C5
    precision = 2 / 3
    """
    retrieved_set = set(retrieved_ids)
    gold_set = set(gold_ids)
    return _safe_divide(len(retrieved_set & gold_set), len(retrieved_set))


def context_recall(retrieved_ids: Iterable[str], gold_ids: Iterable[str]) -> float:
    """
    Of the required/gold chunks, how many did the retriever find?

    Example:
    retrieved = C2, C4, C5
    gold = C2, C5, C7
    recall = 2 / 3
    """
    retrieved_set = set(retrieved_ids)
    gold_set = set(gold_ids)
    return _safe_divide(len(retrieved_set & gold_set), len(gold_set))


def faithfulness_score(answer: str, retrieved_chunks: List[RetrievedChunk]) -> float:
    """
    Estimate whether the answer is grounded in retrieved context.

    This heuristic checks how many meaningful answer tokens appear in the
    retrieved context. It is intentionally simple for a beginner-friendly demo.
    """
    answer_tokens = _content_tokens(answer)
    context_text = " ".join(chunk.text for chunk in retrieved_chunks)
    context_tokens = _content_tokens(context_text)

    if not answer_tokens:
        return 0.0

    return _safe_divide(len(answer_tokens & context_tokens), len(answer_tokens))


def answer_relevancy_score(question: str, answer: str) -> float:
    """
    Estimate whether the answer addresses the question.

    This heuristic measures token overlap between question and answer. In a real
    system this should usually be replaced with a stronger evaluator.
    """
    question_tokens = _content_tokens(question)
    answer_tokens = _content_tokens(answer)

    if not question_tokens:
        return 0.0

    return _safe_divide(len(question_tokens & answer_tokens), len(question_tokens))


def _content_tokens(text: str) -> Set[str]:
    """Remove very common Turkish/English stopwords from token set."""
    stopwords = {
        "ve", "veya", "ile", "bir", "bu", "şu", "için", "mi", "mı", "mu", "mü",
        "ne", "kaç", "hangi", "nasıl", "nedir", "the", "a", "an", "is", "are",
        "of", "to", "in", "for", "and", "or", "on", "with", "by", "as",
    }
    return {token for token in tokenize(text) if token not in stopwords and len(token) > 1}


def evaluate_rag_response(
    question: str,
    answer: str,
    retrieved_chunks: List[RetrievedChunk],
    gold_chunk_ids: List[str],
) -> EvaluationResult:
    """Evaluate a RAG answer against known relevant chunks."""
    retrieved_ids = [chunk.chunk_id for chunk in retrieved_chunks]

    precision = context_precision(retrieved_ids, gold_chunk_ids)
    recall = context_recall(retrieved_ids, gold_chunk_ids)
    faithful = faithfulness_score(answer, retrieved_chunks)
    relevant = answer_relevancy_score(question, answer)

    notes = _build_notes(precision, recall, faithful, relevant)

    return EvaluationResult(
        context_precision=round(precision, 3),
        context_recall=round(recall, 3),
        faithfulness=round(faithful, 3),
        answer_relevancy=round(relevant, 3),
        retrieved_chunk_ids=retrieved_ids,
        gold_chunk_ids=gold_chunk_ids,
        notes=notes,
    )


def _build_notes(precision: float, recall: float, faithful: float, relevant: float) -> str:
    problems = []

    if precision < 0.7:
        problems.append("Retriever alakasız chunk getirmiş olabilir.")
    if recall < 0.7:
        problems.append("Retriever gerekli chunk'lardan bazılarını kaçırmış olabilir.")
    if faithful < 0.8:
        problems.append("Cevap, getirilen context'e yeterince dayanmıyor olabilir.")
    if relevant < 0.4:
        problems.append("Cevap soruyla yeterince ilişkili görünmüyor.")

    if not problems:
        return "Genel olarak retrieval ve cevap üretimi tutarlı görünüyor."

    return " ".join(problems)

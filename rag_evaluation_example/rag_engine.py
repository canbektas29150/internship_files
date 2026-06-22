"""
Simple RAG engine for demonstration purposes.

This file intentionally avoids paid APIs and heavy dependencies. It uses a small
bag-of-words cosine similarity retriever so that the RAG evaluation idea can be
understood without setting up embeddings, vector databases, or an LLM provider.

In a real project, you would replace this retrieval layer with embeddings + a
vector database and replace the simple answer generator with an LLM call.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from ollama_client import chat_with_ollama


_WORD_RE = re.compile(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", re.UNICODE)


@dataclass
class Chunk:
    """A small text unit retrieved by the RAG system."""

    chunk_id: str
    text: str


@dataclass
class RetrievedChunk:
    """A chunk with a similarity score."""

    chunk_id: str
    text: str
    score: float


def tokenize(text: str) -> List[str]:
    """Lowercase and tokenize Turkish/English text."""
    return [token.lower() for token in _WORD_RE.findall(text)]


def cosine_similarity(left_tokens: Iterable[str], right_tokens: Iterable[str]) -> float:
    """Calculate cosine similarity between two token lists."""
    left = Counter(left_tokens)
    right = Counter(right_tokens)

    if not left or not right:
        return 0.0

    common_terms = set(left) & set(right)
    dot_product = sum(left[term] * right[term] for term in common_terms)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def load_text_file(path: str | Path) -> str:
    """Read a UTF-8 text file."""
    return Path(path).read_text(encoding="utf-8")


def split_into_chunks(text: str) -> List[Chunk]:
    """
    Split the document into chunks.

    The sample document uses section headings. This function keeps each section
    as one chunk, which makes evaluation easier because we can assign stable IDs.
    """
    raw_sections = [section.strip() for section in re.split(r"\n\s*---\s*\n", text) if section.strip()]
    chunks: List[Chunk] = []

    for index, section in enumerate(raw_sections, start=1):
        chunks.append(Chunk(chunk_id=f"C{index}", text=section))

    return chunks


def retrieve(question: str, chunks: List[Chunk], top_k: int = 3) -> List[RetrievedChunk]:
    """Return the top-k chunks that are most similar to the question."""
    question_tokens = tokenize(question)
    scored_chunks: List[RetrievedChunk] = []

    for chunk in chunks:
        score = cosine_similarity(question_tokens, tokenize(chunk.text))
        scored_chunks.append(RetrievedChunk(chunk_id=chunk.chunk_id, text=chunk.text, score=score))

    scored_chunks.sort(key=lambda item: item.score, reverse=True)
    return scored_chunks[:top_k]


def _split_sentences(text: str) -> List[str]:
    """Split text into simple sentence-like units."""
    candidates = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [candidate.strip() for candidate in candidates if candidate.strip()]


def generate_extractive_answer(question: str, retrieved_chunks: List[RetrievedChunk]) -> str:
    """
    Generate a basic extractive answer without using any LLM.

    This fallback is useful for debugging retrieval/evaluation logic even when
    Ollama is not running.
    """
    question_tokens = set(tokenize(question))
    best_sentence = ""
    best_score = 0

    for chunk in retrieved_chunks:
        for sentence in _split_sentences(chunk.text):
            sentence_tokens = set(tokenize(sentence))
            overlap = len(question_tokens & sentence_tokens)
            if overlap > best_score:
                best_score = overlap
                best_sentence = sentence

    if not best_sentence:
        return "Bu soruya cevap verecek yeterli bağlam bulunamadı."

    return best_sentence


def generate_ollama_answer(question: str, retrieved_chunks: List[RetrievedChunk]) -> str:
    """Generate an answer using Ollama /api/chat and the configured model."""
    context = "\n\n".join(
        f"[{chunk.chunk_id}] {chunk.text}" for chunk in retrieved_chunks
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Sen bir RAG cevaplayıcısın. Yalnızca verilen context'e dayan. "
                "Context içinde olmayan bilgiyi uydurma. Cevabı kısa, açık ve Türkçe ver. "
                "Mümkünse hangi chunk'a dayandığını parantez içinde belirt."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Context:\n{context}\n\n"
                f"Soru: {question}\n\n"
                "Cevap:"
            ),
        },
    ]

    return chat_with_ollama(messages)


def generate_answer(
    question: str,
    retrieved_chunks: List[RetrievedChunk],
    answer_mode: str = "ollama",
) -> str:
    """Generate an answer either with Ollama or with the local heuristic fallback."""
    if answer_mode == "ollama":
        return generate_ollama_answer(question, retrieved_chunks)

    if answer_mode == "heuristic":
        return generate_extractive_answer(question, retrieved_chunks)

    raise ValueError("answer_mode must be either 'ollama' or 'heuristic'.")

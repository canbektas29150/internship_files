"""
Command-line runner for the RAG evaluation demo.

Run with Ollama / Minimax M3:
    python run_eval.py --answer-mode ollama

Run without any LLM, only for debugging retrieval/evaluation logic:
    python run_eval.py --answer-mode heuristic
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from evaluation import evaluate_rag_response
from ollama_client import get_ollama_settings
from rag_engine import generate_answer, load_text_file, retrieve, split_into_chunks


ROOT_DIR = Path(__file__).resolve().parent
DOCUMENT_PATH = ROOT_DIR / "sample_docs" / "legal_contract.txt"
QUESTIONS_PATH = ROOT_DIR / "data" / "eval_questions.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RAG evaluation demo.")
    parser.add_argument(
        "--answer-mode",
        choices=["ollama", "heuristic"],
        default="ollama",
        help="Use Ollama for answer generation or the local heuristic fallback.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of chunks retrieved for each question.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    document_text = load_text_file(DOCUMENT_PATH)
    chunks = split_into_chunks(document_text)
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))

    if args.answer_mode == "ollama":
        base_url, model = get_ollama_settings()
        print(f"Answer mode: Ollama | base_url={base_url} | model={model}")
    else:
        print("Answer mode: heuristic fallback | no LLM/API call")

    all_results = []

    for index, item in enumerate(questions, start=1):
        question = item["question"]
        gold_chunk_ids = item["gold_chunk_ids"]

        retrieved_chunks = retrieve(question, chunks, top_k=args.top_k)
        answer = generate_answer(question, retrieved_chunks, answer_mode=args.answer_mode)
        result = evaluate_rag_response(question, answer, retrieved_chunks, gold_chunk_ids)
        all_results.append(result)

        print("=" * 80)
        print(f"Question {index}: {question}")
        print(f"Generated answer: {answer}")
        print(f"Retrieved chunks: {result.retrieved_chunk_ids}")
        print(f"Gold chunks:      {result.gold_chunk_ids}")
        print("Scores:")
        print(f"  Context precision: {result.context_precision}")
        print(f"  Context recall:    {result.context_recall}")
        print(f"  Faithfulness:      {result.faithfulness}")
        print(f"  Answer relevancy:  {result.answer_relevancy}")
        print(f"Notes: {result.notes}")

    print("=" * 80)
    print("Average scores")
    print(f"Context precision: {mean(result.context_precision for result in all_results):.3f}")
    print(f"Context recall:    {mean(result.context_recall for result in all_results):.3f}")
    print(f"Faithfulness:      {mean(result.faithfulness for result in all_results):.3f}")
    print(f"Answer relevancy:  {mean(result.answer_relevancy for result in all_results):.3f}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print("\nOllama call failed.")
        print(str(exc))
        print("\nKontrol listesi:")
        print("1. Ollama çalışıyor mu? Terminalde: ollama serve")
        print("2. Model adı doğru mu? .env içindeki OLLAMA_MODEL değerini kontrol et.")
        print("3. Sadece demo mantığını test etmek için: python run_eval.py --answer-mode heuristic")
        raise SystemExit(1)

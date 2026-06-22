"""CLI entry point for Document Intelligence with MiniMax M3 Cloud.

No OpenAI dependency is used. The model call goes through Ollama's native
/api/chat endpoint.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from exporters import save_excel, save_json
from minimax_client import MiniMaxM3Client, OllamaConfig
from pipeline import DocumentIntelligencePipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="document-intelligence-minimaxm3",
        description="Extract structured fields, risks, summaries, and verification from business documents using Ollama Cloud MiniMax M3.",
    )
    parser.add_argument("--input", required=True, help="Path to TXT, PDF, PNG, JPG, WEBP, or TIFF document.")
    parser.add_argument("--out", default="outputs", help="Output folder for JSON and Excel reports.")
    parser.add_argument("--host", default=None, help="Ollama host. Default from OLLAMA_HOST or http://localhost:11434.")
    parser.add_argument("--model", default=None, help="Model name. Default from OLLAMA_MODEL or minimax-m3:cloud.")
    parser.add_argument("--api-key", default=None, help="Ollama Cloud API key for direct https://ollama.com calls.")
    parser.add_argument("--timeout", type=int, default=None, help="Request timeout in seconds.")
    parser.add_argument(
        "--direct-cloud",
        action="store_true",
        help="Shortcut for --host https://ollama.com. Requires OLLAMA_API_KEY or --api-key.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        import os

        host = args.host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        if args.direct_cloud:
            host = "https://ollama.com"

        model = args.model or os.getenv("OLLAMA_MODEL", "minimax-m3:cloud")
        api_key = args.api_key or os.getenv("OLLAMA_API_KEY")
        timeout = args.timeout or int(os.getenv("OLLAMA_TIMEOUT", "120"))

        config = OllamaConfig(host=host, model=model, api_key=api_key, timeout=timeout)
        client = MiniMaxM3Client(config)
        pipeline = DocumentIntelligencePipeline(client)

        result = pipeline.analyze_file(args.input)
        output_dir = Path(args.out)
        json_path = save_json(result, output_dir)
        excel_path = save_excel(result, output_dir)

        analysis = result["analysis"]
        verification = result["verification"]

        print("\nDocument Intelligence Result")
        print("-" * 36)
        print(f"Document type      : {analysis.get('document_type')}")
        print(f"Company/name       : {analysis.get('company_name')}")
        print(f"Document number    : {analysis.get('document_number')}")
        print(f"Date               : {analysis.get('document_date')}")
        print(f"Total amount       : {analysis.get('total_amount')}")
        print(f"Verification score : {verification.get('verification_score')}")
        print(f"Needs review       : {verification.get('needs_human_review')}")
        print(f"\nSaved JSON : {json_path}")
        print(f"Saved Excel: {excel_path}")
        return 0
    except KeyboardInterrupt:
        print("\nCancelled by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

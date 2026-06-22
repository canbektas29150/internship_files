from __future__ import annotations

import argparse
from agent_flow import run_analysis
from resolver import resolve_candidates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="*")
    parser.add_argument("-o", "--output-dir", default="reports")
    args = parser.parse_args()
    prompt = " ".join(args.prompt) if args.prompt else input("Prompt: ")

    candidates = resolve_candidates(prompt)
    if not candidates:
        print("Şirket bulunamadı.")
        return

    if len(candidates) > 1 or candidates[0].source not in {"ticker_exact", "ticker_raw"}:
        print("Bunu mu demek istiyorsun?")
        for i, c in enumerate(candidates, 1):
            print(f"{i}. {c.label} ({c.ticker}) {c.country}")
        choice = int(input("Seçim: "))
        selected = candidates[choice - 1]
    else:
        selected = candidates[0]

    result = run_analysis(prompt, selected.label, selected.ticker, args.output_dir)
    print("\nEXECUTIVE SUMMARY\n")
    print(result["executive_summary"])
    print("\nSCORE\n")
    print(result["score"])
    print("\nSOURCES\n")
    for source in result.get("sources", [])[:5]:
        print("-", source.get("title"), source.get("url"))
    print("\nTRACE\n")
    for step in result.get("trace_steps", []):
        print(f"{step['step']}. {step['name']} - {step['summary']}")


if __name__ == "__main__":
    main()

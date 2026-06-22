"""Export document intelligence results to JSON and Excel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def save_json(result: dict[str, Any], output_dir: str | Path, name: str = "analysis.json") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_excel(result: dict[str, Any], output_dir: str | Path, name: str = "analysis.xlsx") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name

    analysis = result.get("analysis", {})
    verification = result.get("verification", {})

    summary_rows = [
        {"field": "input_path", "value": result.get("input_path")},
        {"field": "document_type", "value": analysis.get("document_type")},
        {"field": "confidence", "value": analysis.get("confidence")},
        {"field": "company_name", "value": analysis.get("company_name")},
        {"field": "document_number", "value": analysis.get("document_number")},
        {"field": "document_date", "value": analysis.get("document_date")},
        {"field": "due_date", "value": analysis.get("due_date")},
        {"field": "tax_number", "value": analysis.get("tax_number")},
        {"field": "total_amount", "value": _money_to_text(analysis.get("total_amount", {}))},
        {"field": "summary", "value": analysis.get("summary")},
        {"field": "verification_score", "value": verification.get("verification_score")},
        {"field": "needs_human_review", "value": verification.get("needs_human_review")},
        {"field": "verifier_notes", "value": verification.get("verifier_notes")},
    ]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="summary")
        pd.DataFrame(analysis.get("parties", [])).to_excel(writer, index=False, sheet_name="parties")
        pd.DataFrame(analysis.get("risky_clauses", [])).to_excel(writer, index=False, sheet_name="risks")
        pd.DataFrame({"recommended_actions": analysis.get("recommended_actions", [])}).to_excel(
            writer, index=False, sheet_name="actions"
        )
        pd.DataFrame({"missing_fields": analysis.get("missing_fields", [])}).to_excel(
            writer, index=False, sheet_name="missing_fields"
        )
        pd.DataFrame(analysis.get("source_evidence", [])).to_excel(writer, index=False, sheet_name="evidence")
        pd.DataFrame({"unsupported_claims": verification.get("unsupported_claims", [])}).to_excel(
            writer, index=False, sheet_name="unsupported"
        )
        pd.DataFrame({"inconsistent_fields": verification.get("inconsistent_fields", [])}).to_excel(
            writer, index=False, sheet_name="inconsistent"
        )

    return path


def _money_to_text(value: dict[str, Any]) -> str:
    if not isinstance(value, dict):
        return ""
    amount = value.get("value")
    currency = value.get("currency")
    if amount is None and not currency:
        return ""
    return f"{amount} {currency or ''}".strip()

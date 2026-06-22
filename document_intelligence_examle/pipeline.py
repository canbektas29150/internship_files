"""Agent-like document intelligence pipeline.

The classes below are deliberately lightweight. They behave like separate
agents without forcing an agent framework dependency:
- DocumentClassifierAgent
- FieldExtractionAgent
- RiskAnalysisAgent
- VerifierAgent
- Export step handled outside
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_reader import compact_text, read_document
from json_utils import extract_json_object
from minimax_client import MiniMaxM3Client
from schemas import DocumentAnalysis, VerificationResult


EXTRACTION_SYSTEM_PROMPT = """
You are a careful document intelligence agent. Extract structured information
from invoices, contracts, forms, receipts, and business documents.

Rules:
- Return ONLY valid JSON.
- Do not invent missing values. Use null or [] when a field is absent.
- Every important extracted field should have short source_evidence when possible.
- If the document is a contract, focus on parties, dates, clause headings, risky clauses, obligations, penalties, termination, confidentiality, liability, and payment terms.
- If the document is an invoice, focus on supplier, customer, invoice number, dates, tax number, totals, currency, due date, line items if visible, and payment terms.
- Keep Turkish text in Turkish and English text in English.
""".strip()


VERIFICATION_SYSTEM_PROMPT = """
You are a verification agent for document extraction.

Compare the extracted JSON against the original document text.
Return ONLY valid JSON.
Mark fields as unsupported if the extracted JSON claims something that cannot be
seen in the document. Mark needs_human_review=true when the source text is weak,
OCR seems noisy, totals are unclear, or risky clauses exist.
""".strip()


ANALYSIS_JSON_TEMPLATE = {
    "document_type": "invoice | contract | form | receipt | unknown",
    "confidence": 0.0,
    "language": "tr | en | unknown",
    "company_name": None,
    "document_number": None,
    "document_date": None,
    "due_date": None,
    "tax_number": None,
    "total_amount": {"value": None, "currency": None},
    "parties": [
        {"name": None, "role": None, "tax_id": None, "address": None}
    ],
    "clause_headings": [],
    "risky_clauses": [
        {"title": None, "risk_level": "low | medium | high | unknown", "reason": None, "evidence": None}
    ],
    "summary": None,
    "recommended_actions": [],
    "missing_fields": [],
    "source_evidence": [
        {"field": "field_name", "evidence_text": "short copied evidence from document"}
    ],
}


VERIFICATION_JSON_TEMPLATE = {
    "verification_score": 0.0,
    "needs_human_review": True,
    "unsupported_claims": [],
    "inconsistent_fields": [],
    "missing_but_important_fields": [],
    "verifier_notes": None,
}


class DocumentIntelligencePipeline:
    def __init__(self, client: MiniMaxM3Client | None = None) -> None:
        self.client = client or MiniMaxM3Client()

    def analyze_file(self, input_path: str | Path) -> dict[str, Any]:
        raw_text = read_document(input_path)
        trimmed_text = compact_text(raw_text)
        analysis = self.extract_fields(trimmed_text)
        verification = self.verify(trimmed_text, analysis)
        return {
            "input_path": str(input_path),
            "raw_text_characters": len(raw_text),
            "prompt_text_characters": len(trimmed_text),
            "analysis": analysis.model_dump(),
            "verification": verification.model_dump(),
        }

    def extract_fields(self, document_text: str) -> DocumentAnalysis:
        prompt = f"""
Extract the document into the exact JSON shape below.
Use null for unknown scalar values and [] for unknown lists.

JSON SHAPE:
{json.dumps(ANALYSIS_JSON_TEMPLATE, ensure_ascii=False, indent=2)}

DOCUMENT TEXT:
{document_text}
""".strip()
        raw = self.client.chat(EXTRACTION_SYSTEM_PROMPT, prompt, temperature=0.05)
        data = extract_json_object(raw)
        return DocumentAnalysis.model_validate(data)

    def verify(self, document_text: str, analysis: DocumentAnalysis) -> VerificationResult:
        prompt = f"""
Verify whether the extracted JSON is supported by the document text.
Return JSON with this exact shape:
{json.dumps(VERIFICATION_JSON_TEMPLATE, ensure_ascii=False, indent=2)}

EXTRACTED JSON:
{analysis.model_dump_json(indent=2)}

DOCUMENT TEXT:
{document_text}
""".strip()
        raw = self.client.chat(VERIFICATION_SYSTEM_PROMPT, prompt, temperature=0.0)
        data = extract_json_object(raw)
        return VerificationResult.model_validate(data)

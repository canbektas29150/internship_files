"""Pydantic schemas for document intelligence outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MoneyAmount(BaseModel):
    value: float | None = None
    currency: str | None = None


class Party(BaseModel):
    name: str | None = None
    role: str | None = None
    tax_id: str | None = None
    address: str | None = None


class RiskyClause(BaseModel):
    title: str | None = None
    risk_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    reason: str | None = None
    evidence: str | None = None


class EvidenceItem(BaseModel):
    field: str
    evidence_text: str


class DocumentAnalysis(BaseModel):
    document_type: str = Field(default="unknown", description="invoice, contract, form, receipt, etc.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    language: str | None = None

    company_name: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    due_date: str | None = None
    tax_number: str | None = None
    total_amount: MoneyAmount = Field(default_factory=MoneyAmount)

    parties: list[Party] = Field(default_factory=list)
    clause_headings: list[str] = Field(default_factory=list)
    risky_clauses: list[RiskyClause] = Field(default_factory=list)
    summary: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    source_evidence: list[EvidenceItem] = Field(default_factory=list)


class VerificationResult(BaseModel):
    verification_score: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_human_review: bool = True
    unsupported_claims: list[str] = Field(default_factory=list)
    inconsistent_fields: list[str] = Field(default_factory=list)
    missing_but_important_fields: list[str] = Field(default_factory=list)
    verifier_notes: str | None = None

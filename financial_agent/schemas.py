from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CompanyCandidate(BaseModel):
    label: str
    ticker: str
    country: str = ""
    confidence: float = 0.0
    source: str = "unknown"


class ResearchPlan(BaseModel):
    company: str
    ticker: str
    objective: str
    focus_areas: List[str] = Field(default_factory=list)
    queries: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)


class ResearchSource(BaseModel):
    query: str
    title: str
    summary: str = ""
    url: str = ""


class AnalystFinding(BaseModel):
    name: str
    status: str = "completed"
    summary: str
    positives: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    data: Dict[str, Any] = Field(default_factory=dict)


class ScoreSummary(BaseModel):
    investment_score: float
    risk_score: float
    risk_level: str
    positives: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    overall: str = "pass"
    warnings: List[str] = Field(default_factory=list)
    checks: List[str] = Field(default_factory=list)


class TraceStep(BaseModel):
    step: int
    name: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)


class FinalReport(BaseModel):
    company: str
    ticker: str
    executive_summary: str
    score: ScoreSummary
    plan: ResearchPlan
    analyst_findings: List[AnalystFinding] = Field(default_factory=list)
    sources: List[ResearchSource] = Field(default_factory=list)
    verification: VerificationResult
    memory_comparison: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    trace_steps: List[TraceStep] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict)

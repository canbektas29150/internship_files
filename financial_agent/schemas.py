from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class CompanyCandidate:
    name: str
    ticker: str
    confidence: float
    reason: str


@dataclass
class ResearchQuery:
    topic: str
    query: str
    source_type: str


@dataclass
class ResearchPlan:
    original_prompt: str
    intent: str
    timeframe: str
    company: CompanyCandidate
    questions_to_answer: List[str]
    queries: List[ResearchQuery]


@dataclass
class SourceItem:
    title: str
    url: str
    snippet: str
    source_type: str


@dataclass
class MetricScore:
    name: str
    value: str
    score: float
    weight: float
    source: str
    explanation: str


@dataclass
class ScoreCard:
    label: str
    total_score: float
    metrics: List[MetricScore]


@dataclass
class AnalystFinding:
    role: str
    assessment: str
    positives: List[str]
    risks: List[str]


@dataclass
class TraceEvent:
    step: str
    input_summary: str
    output_summary: str
    status: str
    timestamp: str


@dataclass
class AgentReport:
    prompt: str
    company: CompanyCandidate
    plan: ResearchPlan
    executive_answer: str
    investment_score: ScoreCard
    risk_score: ScoreCard
    analyst_findings: List[AnalystFinding]
    sources: List[SourceItem]
    data_snapshot: Dict[str, Any]
    verifier_notes: List[str]
    trace_events: List[TraceEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

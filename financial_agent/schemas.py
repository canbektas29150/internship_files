from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


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
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    source_url: str = ""
    validation: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreCard:
    label: str
    total_score: float
    metrics: List[MetricScore]
    evidence_map: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


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
    parent_step: str = ""
    goal: str = ""
    tool: str = ""
    data_source: str = ""
    source_url: str = ""
    latency_ms: float = 0.0
    confidence: float = 0.0
    decision: Dict[str, Any] = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)
    validation: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    requested_fields: List[str] = field(default_factory=list)
    returned_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    records_returned: int = 0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    source_quality: List[Dict[str, Any]] = field(default_factory=list)
    claim_checks: List[Dict[str, Any]] = field(default_factory=list)


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

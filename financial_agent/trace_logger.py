from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from schemas import TraceEvent


def _short(value: Any, limit: int = 4000) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text[:limit]


class TraceLogger:
    """Local explainability logger for the financial agent.

    This logger intentionally does not depend on Langfuse or any external
    service. It records every agent step into memory and writes JSONL rows
    into logs/trace_events.jsonl. The extra fields are designed for debugging:
    decisions, reasoning, validations, source quality, evidence mapping and
    claim checks.
    """

    def __init__(self, run_name: str = "financial-agent-run") -> None:
        self.run_name = run_name
        self.events: List[TraceEvent] = []
        self.log_dir = Path("logs")
        self.log_file = self.log_dir / "trace_events.jsonl"

    @contextmanager
    def step(
        self,
        step: str,
        input_summary: Any,
        *,
        goal: str = "",
        parent_step: str = "",
        tool: str = "",
        data_source: str = "",
        source_url: str = "",
    ) -> Iterator[Dict[str, Any]]:
        """Context manager that records duration and errors automatically.

        The yielded dictionary can be filled by the caller with keys such as
        output_summary, decision, reasoning, validation and records_returned.
        """
        started = time.perf_counter()
        ctx: Dict[str, Any] = {
            "output_summary": "",
            "status": "ok",
            "confidence": 0.0,
            "decision": {},
            "reasoning": [],
            "validation": {},
            "warnings": [],
            "requested_fields": [],
            "returned_fields": [],
            "missing_fields": [],
            "records_returned": 0,
            "evidence": [],
            "source_quality": [],
            "claim_checks": [],
        }
        try:
            yield ctx
        except Exception as exc:
            ctx["status"] = "error"
            ctx["output_summary"] = f"ERROR: {exc}"
            ctx.setdefault("warnings", []).append(str(exc))
            raise
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            self.add(
                step=step,
                input_summary=input_summary,
                output_summary=ctx.get("output_summary", f"{step} completed"),
                status=ctx.get("status", "ok"),
                parent_step=parent_step,
                goal=goal,
                tool=tool,
                data_source=data_source,
                source_url=source_url,
                latency_ms=latency_ms,
                confidence=float(ctx.get("confidence") or 0.0),
                decision=ctx.get("decision") or {},
                reasoning=list(ctx.get("reasoning") or []),
                validation=ctx.get("validation") or {},
                warnings=list(ctx.get("warnings") or []),
                requested_fields=list(ctx.get("requested_fields") or []),
                returned_fields=list(ctx.get("returned_fields") or []),
                missing_fields=list(ctx.get("missing_fields") or []),
                records_returned=int(ctx.get("records_returned") or 0),
                evidence=list(ctx.get("evidence") or []),
                source_quality=list(ctx.get("source_quality") or []),
                claim_checks=list(ctx.get("claim_checks") or []),
            )

    def add(
        self,
        step: str,
        input_summary: Any,
        output_summary: Any,
        status: str = "ok",
        *,
        parent_step: str = "",
        goal: str = "",
        tool: str = "",
        data_source: str = "",
        source_url: str = "",
        latency_ms: float = 0.0,
        confidence: float = 0.0,
        decision: Optional[Dict[str, Any]] = None,
        reasoning: Optional[List[str]] = None,
        validation: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        requested_fields: Optional[List[str]] = None,
        returned_fields: Optional[List[str]] = None,
        missing_fields: Optional[List[str]] = None,
        records_returned: int = 0,
        evidence: Optional[List[Dict[str, Any]]] = None,
        source_quality: Optional[List[Dict[str, Any]]] = None,
        claim_checks: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        event = TraceEvent(
            step=step,
            input_summary=_short(input_summary, 2500),
            output_summary=_short(output_summary, 5000),
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            parent_step=parent_step,
            goal=goal,
            tool=tool,
            data_source=data_source,
            source_url=source_url,
            latency_ms=latency_ms,
            confidence=round(float(confidence or 0.0), 3),
            decision=decision or {},
            reasoning=reasoning or [],
            validation=validation or {},
            warnings=warnings or [],
            requested_fields=requested_fields or [],
            returned_fields=returned_fields or [],
            missing_fields=missing_fields or [],
            records_returned=records_returned,
            evidence=evidence or [],
            source_quality=source_quality or [],
            claim_checks=claim_checks or [],
        )
        self.events.append(event)
        self.log_dir.mkdir(exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    def to_report(self) -> Dict[str, Any]:
        events = [asdict(e) for e in self.events]
        warnings = [w for e in self.events for w in e.warnings]
        failed = [e for e in self.events if e.status != "ok"]
        avg_conf = round(
            sum(e.confidence for e in self.events if e.confidence) /
            max(1, len([e for e in self.events if e.confidence])),
            3,
        )
        return {
            "run_name": self.run_name,
            "events_count": len(self.events),
            "failed_steps": [e.step for e in failed],
            "warnings_count": len(warnings),
            "average_confidence": avg_conf,
            "log_file": str(self.log_file),
        }

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List
from schemas import TraceEvent


class TraceLogger:
    def __init__(self, run_name: str = "financial-agent-run") -> None:
        self.run_name = run_name
        self.events: List[TraceEvent] = []
        self.log_dir = Path("logs")
        self.log_file = self.log_dir / "trace_events.jsonl"

    def add(self, step: str, input_summary: str, output_summary: str, status: str = "ok") -> None:
        event = TraceEvent(
            step=step,
            input_summary=str(input_summary)[:1500],
            output_summary=str(output_summary)[:2500],
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.events.append(event)
        self.log_dir.mkdir(exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    @contextmanager
    def step(self, step: str, input_summary: str) -> Iterator[None]:
        try:
            yield
        except Exception as exc:
            self.add(step, input_summary, f"ERROR: {exc}", status="error")
            raise

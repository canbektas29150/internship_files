"""Utilities for extracting JSON from LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from a model response.

    The model is instructed to return pure JSON, but this helper also handles
    fenced code blocks or short explanations around the JSON.
    """
    cleaned = raw.strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)

    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse JSON from model response. Raw response:\n{raw}") from exc

"""
Small Ollama client used by the RAG demo.

This project intentionally uses Ollama's native REST API, not the OpenAI Python
SDK. It works with a local Ollama server and with cloud models that are exposed
through your Ollama installation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "minimax-m3"


def load_dotenv(path: str | Path = ROOT_DIR / ".env") -> None:
    """Load a tiny .env file without adding python-dotenv as a dependency."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_ollama_settings() -> tuple[str, str]:
    """Return base URL and model name from environment variables."""
    load_dotenv()
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    return base_url, model


def chat_with_ollama(
    messages: List[Dict[str, str]],
    *,
    model: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.1,
    timeout_seconds: int = 120,
) -> str:
    """
    Generate a chat response through Ollama's native /api/chat endpoint.

    Parameters are deliberately simple so the code is easy to understand.
    """
    configured_base_url, configured_model = get_ollama_settings()
    base_url = (base_url or configured_base_url).rstrip("/")
    model = model or configured_model

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    response = requests.post(
        f"{base_url}/api/chat",
        json=payload,
        timeout=timeout_seconds,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "Ollama request failed. "
            f"Status={response.status_code}, body={response.text[:500]}"
        )

    data = response.json()
    message = data.get("message", {})
    content = message.get("content", "")

    if not content.strip():
        raise RuntimeError(f"Ollama returned an empty response: {json.dumps(data)[:500]}")

    return content.strip()

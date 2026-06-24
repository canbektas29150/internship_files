from __future__ import annotations

import os
from typing import Optional
import requests


def call_ollama(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Ollama chat endpointi. OpenAI API kullanılmaz."""
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "minimax-m3")
    url = f"{base_url}/api/chat"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }

    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content")
    except Exception:
        return None

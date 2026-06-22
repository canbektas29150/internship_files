"""Minimal Ollama / MiniMax M3 Cloud client.

This module intentionally avoids OpenAI SDKs. It talks to Ollama's native
`/api/chat` endpoint either through a local Ollama daemon or directly through
https://ollama.com with an API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv


@dataclass(frozen=True)
class OllamaConfig:
    """Runtime configuration for Ollama Cloud access.

    Two common modes:
    1. Local cloud route:
       host=http://localhost:11434, model=minimax-m3:cloud
       Requires `ollama signin` on the machine.

    2. Direct cloud route:
       host=https://ollama.com, model=minimax-m3 or minimax-m3:cloud
       Requires OLLAMA_API_KEY.
    """

    host: str
    model: str
    api_key: str | None = None
    timeout: int = 120

    @property
    def chat_url(self) -> str:
        return self.host.rstrip("/") + "/api/chat"


class MiniMaxM3Client:
    """Small wrapper around the Ollama chat endpoint."""

    def __init__(self, config: OllamaConfig | None = None) -> None:
        load_dotenv()
        if config is None:
            config = OllamaConfig(
                host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", "minimax-m3:cloud"),
                api_key=os.getenv("OLLAMA_API_KEY"),
                timeout=int(os.getenv("OLLAMA_TIMEOUT", "120")),
            )
        self.config = config

    def chat(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.1) -> str:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key and "ollama.com" in self.config.host:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            response = requests.post(
                self.config.chat_url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = exc.response.text[:1200] if exc.response is not None else ""
            raise RuntimeError(
                f"Ollama request failed with HTTP error: {exc}. Response: {detail}"
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(
                "Could not reach Ollama. Check OLLAMA_HOST, internet connection, "
                "`ollama serve`, or direct cloud API key."
            ) from exc

        data = response.json()
        message = data.get("message", {})
        content = message.get("content")
        if not content:
            raise RuntimeError(f"Ollama returned no message content. Raw response: {data}")
        return content

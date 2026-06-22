"""DeepWiki Repo Analyzer with MiniMax M3 Cloud.

This CLI connects to the public DeepWiki MCP server, collects repository-grounded
context, and asks MiniMax M3 through Ollama Cloud/Ollama's native chat API to
format the final answer.

No OpenAI API, OpenAI Agents SDK, or OpenAI tracing is used.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is optional at runtime
    load_dotenv = None

if load_dotenv:
    load_dotenv()

AnalysisMode = Literal[
    "overview",
    "language",
    "architecture",
    "setup",
    "risks",
    "contribution",
    "custom",
]

DEEPWIKI_MCP_URL = "https://mcp.deepwiki.com/mcp"
DEFAULT_LOCAL_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_DIRECT_CLOUD_HOST = "https://ollama.com"
DEFAULT_LOCAL_CLOUD_MODEL = "minimax-m3:cloud"
DEFAULT_DIRECT_CLOUD_MODEL = "minimax-m3"

MODE_PROMPTS: dict[str, str] = {
    "overview": "Summarize what this repository does, who it is for, and the most important files or modules.",
    "language": "Identify the primary programming language and explain the evidence from the repository structure.",
    "architecture": "Explain the repository architecture: important folders, execution flow, and how the main components interact.",
    "setup": "Explain how to install, configure, and run this project locally. Mention missing or unclear steps if any.",
    "risks": "Review the repository for possible maintenance, security, dependency, or documentation risks.",
    "contribution": "Explain how a new contributor should approach this repository and where they should start reading.",
}


@dataclass(frozen=True)
class AnalyzerConfig:
    repo: str
    mode: AnalysisMode
    question: str | None
    mcp_timeout: float
    llm_timeout: float
    ollama_host: str
    ollama_model: str
    ollama_api_key: str | None
    raw_mcp: bool


class OllamaCloudClient:
    """Small async client for Ollama's native /api/chat endpoint.

    This works with:
    - Local Ollama host running a cloud model, e.g. http://localhost:11434 + minimax-m3:cloud
    - Direct Ollama Cloud API, e.g. https://ollama.com + minimax-m3 + OLLAMA_API_KEY
    """

    def __init__(self, host: str, model: str, api_key: str | None, timeout: float) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.host}/api/chat", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        message = data.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"].strip()
        if isinstance(data.get("response"), str):
            return data["response"].strip()
        raise RuntimeError(f"Unexpected Ollama response format: {data}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepwiki-repo-analyzer",
        description="Analyze GitHub repositories through DeepWiki MCP and MiniMax M3 Cloud.",
    )
    parser.add_argument(
        "--repo",
        default="openai/codex",
        help="GitHub repository in owner/name format. Example: openai/codex",
    )
    parser.add_argument(
        "--mode",
        choices=list(MODE_PROMPTS.keys()) + ["custom"],
        default="overview",
        help="Prebuilt analysis mode.",
    )
    parser.add_argument(
        "--question",
        help="Custom question. Required when --mode custom. Optional extra instruction for other modes.",
    )
    parser.add_argument(
        "--mcp-timeout",
        type=float,
        default=float(os.getenv("MCP_TIMEOUT", "90")),
        help="Timeout in seconds for DeepWiki MCP calls.",
    )
    parser.add_argument(
        "--llm-timeout",
        type=float,
        default=float(os.getenv("LLM_TIMEOUT", "120")),
        help="Timeout in seconds for the MiniMax/Ollama chat call.",
    )
    parser.add_argument(
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or DEFAULT_LOCAL_OLLAMA_HOST,
        help="Ollama API host. Default: local Ollama at http://localhost:11434",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OLLAMA_MODEL") or DEFAULT_LOCAL_CLOUD_MODEL,
        help="Ollama model name. Default: minimax-m3:cloud",
    )
    parser.add_argument(
        "--direct-cloud",
        action="store_true",
        help="Use Ollama Cloud directly at https://ollama.com/api/chat. Requires OLLAMA_API_KEY.",
    )
    parser.add_argument(
        "--raw-mcp",
        action="store_true",
        help="Print the raw DeepWiki MCP answer without sending it to MiniMax M3.",
    )
    return parser


def validate_repo(repo: str) -> str:
    cleaned = repo.strip().removeprefix("https://github.com/").strip("/")
    parts = cleaned.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Repo must be in 'owner/name' format, for example 'openai/codex'.")
    return cleaned


def build_task(config: AnalyzerConfig) -> str:
    if config.mode == "custom":
        if not config.question:
            raise ValueError("--question is required when --mode custom.")
        return config.question

    task = MODE_PROMPTS[config.mode]
    if config.question:
        task += f"\nAdditional user request: {config.question}"
    return task


def result_to_text(result: Any) -> str:
    """Convert MCP CallToolResult-like objects into readable text."""
    content = getattr(result, "content", None)
    if not content:
        return str(result)

    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
        else:
            parts.append(str(item))
    return "\n".join(parts).strip()


async def call_deepwiki(repo: str, task: str, timeout: float) -> str:
    """Ask DeepWiki MCP for repository-grounded context."""
    async with streamablehttp_client(
        DEEPWIKI_MCP_URL,
        timeout=timeout,
        sse_read_timeout=timeout,
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # The DeepWiki server exposes ask_question(repoName, question).
            # This is usually more token-efficient than pulling the whole wiki.
            result = await session.call_tool(
                "ask_question",
                {
                    "repoName": repo,
                    "question": task,
                },
            )
            return result_to_text(result)


def build_minimax_prompts(repo: str, task: str, mcp_context: str) -> tuple[str, str]:
    system_prompt = """
You are a repository analysis assistant.
You receive repository-grounded context from the DeepWiki MCP server.
Base your answer only on that context and be explicit when information is missing.
Do not invent file names, commands, dependencies, risks, or architecture details.
Write for a developer who wants to understand the project quickly.
""".strip()

    user_prompt = f"""
Repository: {repo}
Task: {task}

DeepWiki MCP context:
{mcp_context}

Return the answer in this format:
1. Direct answer
2. Evidence from repository
3. Practical notes for a developer
4. Uncertainties or missing information
""".strip()
    return system_prompt, user_prompt


async def run_analysis(config: AnalyzerConfig) -> str:
    task = build_task(config)
    mcp_context = await call_deepwiki(config.repo, task, config.mcp_timeout)

    if config.raw_mcp:
        return mcp_context

    client = OllamaCloudClient(
        host=config.ollama_host,
        model=config.ollama_model,
        api_key=config.ollama_api_key,
        timeout=config.llm_timeout,
    )
    system_prompt, user_prompt = build_minimax_prompts(config.repo, task, mcp_context)
    return await client.chat(system_prompt, user_prompt)


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        repo = validate_repo(args.repo)

        ollama_host = args.ollama_host
        ollama_model = args.model
        ollama_api_key = os.getenv("OLLAMA_API_KEY")

        if args.direct_cloud:
            ollama_host = DEFAULT_DIRECT_CLOUD_HOST
            # Direct Ollama Cloud API uses the hosted model name without the local :cloud suffix.
            # This also protects users who copied .env.example and left OLLAMA_MODEL=minimax-m3:cloud.
            if ollama_model.endswith(":cloud"):
                ollama_model = ollama_model.removesuffix(":cloud")
            if not ollama_api_key:
                raise ValueError("--direct-cloud requires OLLAMA_API_KEY to be set.")

        config = AnalyzerConfig(
            repo=repo,
            mode=args.mode,
            question=args.question,
            mcp_timeout=args.mcp_timeout,
            llm_timeout=args.llm_timeout,
            ollama_host=ollama_host,
            ollama_model=ollama_model,
            ollama_api_key=ollama_api_key,
            raw_mcp=args.raw_mcp,
        )

        output = await run_analysis(config)
        print(output)
        return 0
    except KeyboardInterrupt:
        print("\nCancelled by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()

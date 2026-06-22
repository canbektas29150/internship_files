"""DeepWiki Repo Analyzer Agent.

A small CLI project that connects an OpenAI Agent to the public DeepWiki MCP
Streamable HTTP server. It turns a basic one-question demo into a reusable
repository analysis tool.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import Literal

from agents import Agent, Runner, gen_trace_id, trace
from agents.mcp import MCPServerStreamableHttp

AnalysisMode = Literal["overview", "language", "architecture", "setup", "risks", "contribution", "custom"]

DEEPWIKI_MCP_URL = "https://mcp.deepwiki.com/mcp"

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
    timeout: int
    show_trace: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepwiki-repo-analyzer",
        description="Analyze GitHub repositories through the DeepWiki MCP server using OpenAI Agents.",
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
        "--timeout",
        type=int,
        default=20,
        help="HTTP client timeout in seconds for the MCP server.",
    )
    parser.add_argument(
        "--hide-trace",
        action="store_true",
        help="Do not print the OpenAI trace URL.",
    )
    return parser


def validate_repo(repo: str) -> str:
    cleaned = repo.strip().removeprefix("https://github.com/").strip("/")
    parts = cleaned.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Repo must be in 'owner/name' format, for example 'openai/codex'.")
    return cleaned


def build_user_request(config: AnalyzerConfig) -> str:
    if config.mode == "custom":
        if not config.question:
            raise ValueError("--question is required when --mode custom.")
        task = config.question
    else:
        task = MODE_PROMPTS[config.mode]
        if config.question:
            task += f"\nAdditional user request: {config.question}"

    return f"""
Repository: {config.repo}
Task: {task}

Return the answer in this format:
1. Direct answer
2. Evidence from repository
3. Practical notes for a developer
4. Uncertainties or missing information
""".strip()


def build_agent(server: MCPServerStreamableHttp) -> Agent:
    instructions = """
You are a repository analysis assistant connected to DeepWiki MCP tools.

Rules:
- Prefer information gathered through MCP tools over assumptions.
- Be clear when the repository does not expose enough information.
- Keep the answer useful for a developer who wants to understand the project quickly.
- Mention concrete files, folders, dependencies, or commands when available.
- Do not invent repository details that were not found through the tools.
""".strip()

    return Agent(
        name="DeepWiki Repo Analyzer",
        instructions=instructions,
        mcp_servers=[server],
    )


async def run_analysis(config: AnalyzerConfig) -> str:
    request = build_user_request(config)

    async with MCPServerStreamableHttp(
        name="DeepWiki MCP Streamable HTTP Server",
        params={
            "url": DEEPWIKI_MCP_URL,
            "timeout": config.timeout,
            "sse_read_timeout": 300,
        },
        max_retry_attempts=2,
        retry_backoff_seconds_base=2.0,
        client_session_timeout_seconds=config.timeout,
    ) as server:
        agent = build_agent(server)
        trace_id = gen_trace_id()

        with trace(workflow_name="DeepWiki Repo Analyzer", trace_id=trace_id):
            if config.show_trace:
                print(f"Trace: https://platform.openai.com/traces/trace?trace_id={trace_id}\n")
            result = await Runner.run(agent, request)
            return result.final_output


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        repo = validate_repo(args.repo)
        config = AnalyzerConfig(
            repo=repo,
            mode=args.mode,
            question=args.question,
            timeout=args.timeout,
            show_trace=not args.hide_trace,
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

"""Client demo for using MCP prompts as dynamic OpenAI Agents instructions.

Run:
    uv run main.py --prompt review --focus "security vulnerabilities"

The script starts server.py locally, connects to its Streamable HTTP endpoint,
fetches an instruction prompt, and then runs an agent with those instructions.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

from agents import Agent, Runner, gen_trace_id, trace
from agents.mcp import MCPServer, MCPServerStreamableHttp
from agents.model_settings import ModelSettings

STREAMABLE_HTTP_HOST = os.getenv("STREAMABLE_HTTP_HOST", "127.0.0.1")

DEFAULT_REVIEW_CODE = """Please review this Python code:

import os

def process_user_input(user_input):
    command = f"echo {user_input}"
    os.system(command)
    return "Command executed"
"""

PROMPT_MAP = {
    "review": "generate_code_review_instructions",
    "refactor": "generate_refactor_instructions",
    "explain": "generate_explanation_instructions",
}


def choose_port() -> int:
    """Use STREAMABLE_HTTP_PORT when provided, otherwise find a free local port."""
    env_port = os.getenv("STREAMABLE_HTTP_PORT")
    if env_port:
        return int(env_port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((STREAMABLE_HTTP_HOST, 0))
        address = cast(tuple[str, int], sock.getsockname())
        return address[1]


def wait_for_port(host: str, port: int, timeout_seconds: float = 8.0) -> None:
    """Wait until the local MCP server starts accepting TCP connections."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"MCP server did not start on {host}:{port}")


def read_user_input(args: argparse.Namespace) -> str:
    """Load review text from --code-file or use a built-in vulnerable example."""
    if args.code_file:
        code_path = Path(args.code_file)
        return f"Please analyze this code from {code_path.name}:\n\n{code_path.read_text(encoding='utf-8')}"
    return args.message or DEFAULT_REVIEW_CODE


async def get_instructions_from_prompt(
    mcp_server: MCPServer,
    prompt_name: str,
    arguments: dict[str, str],
) -> str:
    """Call an MCP prompt and return its first text message."""
    prompt_result = await mcp_server.get_prompt(prompt_name, arguments)
    if not prompt_result.messages:
        raise RuntimeError(f"Prompt {prompt_name!r} returned no messages")

    content = prompt_result.messages[0].content
    return content.text if hasattr(content, "text") else str(content)


async def show_available_prompts(mcp_server: MCPServer) -> None:
    """Print prompt names so users can see what the MCP server exposes."""
    prompts_result = await mcp_server.list_prompts()
    print("Available MCP prompts:")
    for prompt in prompts_result.prompts:
        print(f"- {prompt.name}: {prompt.description}")
    print()


async def run_agent_demo(args: argparse.Namespace, mcp_url: str) -> None:
    """Connect to the MCP server, fetch instructions, and run the agent."""
    async with MCPServerStreamableHttp(
        name="Local Prompt Server",
        params={"url": mcp_url},
    ) as server:
        await show_available_prompts(server)

        prompt_name = PROMPT_MAP[args.prompt]
        prompt_arguments = {
            "focus": args.focus,
            "target": args.focus,
            "topic": args.topic,
            "audience": args.audience,
            "language": args.language,
        }
        instructions = await get_instructions_from_prompt(server, prompt_name, prompt_arguments)

        agent = Agent(
            name="MCP Prompt Agent",
            instructions=instructions,
            model_settings=ModelSettings(tool_choice="auto"),
        )

        user_input = read_user_input(args)
        trace_id = gen_trace_id()
        print(f"Trace URL: https://platform.openai.com/traces/trace?trace_id={trace_id}\n")

        with trace(workflow_name="MCP Prompt Agent Demo", trace_id=trace_id):
            result = await Runner.run(starting_agent=agent, input=user_input)

        print("Agent output:\n")
        print(result.final_output)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MCP prompt-driven agent demo")
    parser.add_argument("--prompt", choices=PROMPT_MAP.keys(), default="review")
    parser.add_argument("--focus", default="security vulnerabilities")
    parser.add_argument("--language", default="python")
    parser.add_argument("--topic", default="MCP prompts")
    parser.add_argument("--audience", default="beginner")
    parser.add_argument("--message", help="Text to send to the agent")
    parser.add_argument("--code-file", help="Path of a code file to analyze")
    parser.add_argument("--keep-server-open", action="store_true")
    return parser


def main() -> None:
    if not shutil.which("uv"):
        raise RuntimeError("uv is not installed. Install it first: https://docs.astral.sh/uv/")

    args = build_arg_parser().parse_args()
    port = choose_port()
    mcp_url = f"http://{STREAMABLE_HTTP_HOST}:{port}/mcp"

    project_dir = Path(__file__).resolve().parent
    server_file = project_dir / "server.py"
    env = os.environ.copy()
    env["STREAMABLE_HTTP_HOST"] = STREAMABLE_HTTP_HOST
    env["STREAMABLE_HTTP_PORT"] = str(port)

    process: subprocess.Popen[Any] | None = None
    try:
        print(f"Starting MCP server at {mcp_url}")
        process = subprocess.Popen(["uv", "run", str(server_file)], cwd=project_dir, env=env)
        wait_for_port(STREAMABLE_HTTP_HOST, port)
        asyncio.run(run_agent_demo(args, mcp_url))
    finally:
        if process and not args.keep_server_open:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            print("\nMCP server stopped.")
        elif process:
            print(f"\nMCP server is still running at {mcp_url}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Interrupted by user")

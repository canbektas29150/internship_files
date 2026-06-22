"""MCP prompt server for reusable agent instruction templates.

This server exposes prompts over Streamable HTTP. The client in main.py calls
these prompts first, then uses the returned text as dynamic agent instructions.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

STREAMABLE_HTTP_HOST = os.getenv("STREAMABLE_HTTP_HOST", "127.0.0.1")
STREAMABLE_HTTP_PORT = int(os.getenv("STREAMABLE_HTTP_PORT", "18080"))

mcp = FastMCP(
    "Prompt Server",
    host=STREAMABLE_HTTP_HOST,
    port=STREAMABLE_HTTP_PORT,
)


def _safe_text(value: str, default: str) -> str:
    """Keep prompt arguments short and predictable for demo usage."""
    cleaned = (value or default).strip()
    return cleaned[:120] if cleaned else default


@mcp.prompt()
def generate_code_review_instructions(
    focus: str = "general code quality",
    language: str = "python",
) -> str:
    """Generate instruction text for a code review agent."""
    focus = _safe_text(focus, "general code quality")
    language = _safe_text(language, "python")

    return f"""You are a senior {language} code review specialist.

Goal:
Review the user's code with extra attention to {focus}.

Rules:
- Point out concrete bugs, risks, and maintainability problems.
- Explain why each issue matters.
- Suggest small, practical fixes before larger rewrites.
- Include corrected code only when it makes the feedback clearer.
- Avoid vague comments like "improve quality" without an example.

Response format:
1. Overall assessment
2. Issues found
3. Security and reliability notes
4. Suggested improvements
5. Cleaned-up example, if useful
"""


@mcp.prompt()
def generate_refactor_instructions(
    target: str = "readability",
    language: str = "python",
) -> str:
    """Generate instruction text for a refactoring agent."""
    target = _safe_text(target, "readability")
    language = _safe_text(language, "python")

    return f"""You are a pragmatic {language} refactoring assistant.

Goal:
Refactor code mainly for {target} while preserving behavior.

Rules:
- Keep the solution beginner-friendly.
- Prefer clear names, simple functions, and explicit error handling.
- Do not introduce unnecessary frameworks.
- Mention any behavior change separately.
- Return the final code in one complete block when asked to rewrite.
"""


@mcp.prompt()
def generate_explanation_instructions(
    audience: str = "beginner",
    topic: str = "MCP prompts",
) -> str:
    """Generate instruction text for explaining technical code or concepts."""
    audience = _safe_text(audience, "beginner")
    topic = _safe_text(topic, "MCP prompts")

    return f"""You explain {topic} to a {audience} audience.

Rules:
- Start with the purpose, then describe the flow step by step.
- Use short examples.
- Explain new terms before using them heavily.
- Avoid pretending the code does more than it actually does.
"""


@mcp.tool()
def current_utc_time() -> str:
    """Return the current UTC time for demos that need a simple MCP tool."""
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

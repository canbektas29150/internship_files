import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

BASE_DIR = Path(__file__).parent
SAMPLE_FILES_DIR = BASE_DIR / "sample_files"


def create_agent(mcp_server):
    return Agent(
        name="Simple Filesystem Assistant",
        instructions="""
        You answer questions using only the files inside sample_files.

        Rules:
        - Use MCP filesystem tools before answering file questions.
        - If the answer is not in the files, say you could not find it.
        - Keep answers short.
        """,
        mcp_servers=[mcp_server],
    )


async def show_tools(server):
    tools = await server.list_tools()
    print("\nAvailable MCP tools:")
    for tool in tools:
        print(f"- {tool.name}")
    print()


async def ask(agent, question):
    result = await Runner.run(starting_agent=agent, input=question)
    print("\nAnswer:")
    print(result.final_output)
    print()


async def chat(agent):
    print("Simple MCP Filesystem Agent")
    print("Ask questions about sample_files/. Type exit to quit.\n")

    while True:
        question = input("Question > ").strip()

        if question.lower() in {"exit", "quit"}:
            break

        if question:
            await ask(agent, question)


async def main():
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--question", type=str, help="Ask one question and exit.")
    parser.add_argument("--tools", action="store_true", help="Show MCP tools and exit.")
    args = parser.parse_args()

    async with MCPServerStdio(
        name="Filesystem MCP Server",
        params={
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(SAMPLE_FILES_DIR),
            ],
        },
        cache_tools_list=True,
    ) as server:
        if args.tools:
            await show_tools(server)
            return

        agent = create_agent(server)

        if args.question:
            await ask(agent, args.question)
            return

        await show_tools(server)
        await chat(agent)


if __name__ == "__main__":
    asyncio.run(main())

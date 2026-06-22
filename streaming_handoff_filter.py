from __future__ import annotations

import json
import random

from agents import Agent, HandoffInputData, Runner, function_tool, handoff, trace
from agents.extensions import handoff_filters
from agents.models import is_gpt_5_default


MAX_HISTORY_ITEMS = 5


@function_tool
def random_number_tool(max: int) -> int:
    """Return a random integer between 0 and max."""
    if max < 0:
        raise ValueError("max must be non-negative")
    return random.randint(0, max)


def spanish_handoff_message_filter(handoff_message_data: HandoffInputData) -> HandoffInputData:
    """Clean the conversation before it is passed to the Spanish agent.

    The same filter can be used in normal and streaming runs.
    """
    if is_gpt_5_default():
        print("gpt-5 is enabled, so the input history is not filtered.")
        return handoff_message_data

    cleaned_data = handoff_filters.remove_all_tools(handoff_message_data)

    history = cleaned_data.input_history
    if isinstance(history, tuple):
        history = history[-MAX_HISTORY_ITEMS:]

    return HandoffInputData(
        input_history=history,
        pre_handoff_items=tuple(cleaned_data.pre_handoff_items),
        new_items=tuple(cleaned_data.new_items),
    )


first_agent = Agent(
    name="General Assistant",
    instructions="Be extremely concise.",
    tools=[random_number_tool],
)

spanish_agent = Agent(
    name="Spanish Assistant",
    instructions="Only answer in Spanish. Be concise and clear.",
    handoff_description="A Spanish-speaking assistant.",
)

second_agent = Agent(
    name="Handoff Router",
    instructions="Be helpful. If the user speaks Spanish, hand off to the Spanish assistant.",
    handoffs=[handoff(spanish_agent, input_filter=spanish_handoff_message_filter)],
)


async def main() -> None:
    with trace(workflow_name="Streaming handoff message filtering"):
        result = await Runner.run(first_agent, input="Hi, my name is Sora.")
        print("Step 1 done")

        result = await Runner.run(
            first_agent,
            input=result.to_input_list()
            + [{"content": "Can you generate a random number between 0 and 100?", "role": "user"}],
        )
        print("Step 2 done")

        result = await Runner.run(
            second_agent,
            input=result.to_input_list()
            + [{"content": "I live in New York City. What is the population of the city?", "role": "user"}],
        )
        print("Step 3 done")

        stream_result = Runner.run_streamed(
            second_agent,
            input=result.to_input_list()
            + [{"content": "Por favor habla en español. ¿Cuál es mi nombre y dónde vivo?", "role": "user"}],
        )

        async for event in stream_result.stream_events():
            if event.type == "raw_response_event":
                continue
            print(f"[stream event] {event.type}")

        print("Step 4 done")

    print("\n=== Final messages after streaming handoff filtering ===\n")
    for item in stream_result.to_input_list():
        print(json.dumps(item, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

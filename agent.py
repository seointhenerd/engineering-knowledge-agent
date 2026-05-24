"""Agent loop: Claude decides which tools to call, iterates until a final answer."""

import os

import anthropic
from rich.console import Console

from tools import TOOL_DEFINITIONS, run_tool

console = Console()

SYSTEM_PROMPT = (
    "You are a precise engineering assistant. You have access to tools to search "
    "local technical documents and the web. Use search_documents first for questions "
    "about specific hardware or specs in the knowledge base. Use search_web for "
    "current information or topics not covered locally. Use summarize_document when "
    "the user explicitly asks for an overview or summary of a file. "
    "Always cite your sources. Never hallucinate specifications, values, or facts."
)

MAX_ITERATIONS = 10


def run_agent(question: str) -> tuple[str, list[str]]:
    """Returns (answer, tools_used)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set. Create a .env file.")

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": question}]
    tools_used: list[str] = []

    for iteration in range(MAX_ITERATIONS):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Claude returned a final answer
        if response.stop_reason == "end_turn":
            return _extract_text(response), tools_used

        # Claude wants to call tools
        if response.stop_reason == "tool_use":
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            tool_results = []

            for call in tool_calls:
                console.print(f"  [dim]→ calling [bold]{call.name}[/bold]({_fmt_inputs(call.input)})[/dim]")
                result = run_tool(call.name, call.input)
                if call.name not in tools_used:
                    tools_used.append(call.name)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": result,
                })

            # Append Claude's response and the tool results to the conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        break

    return "Agent reached iteration limit without a final answer.", tools_used


def _extract_text(response) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def _fmt_inputs(inputs: dict) -> str:
    return ", ".join(f"{k}={repr(v)}" for k, v in inputs.items())

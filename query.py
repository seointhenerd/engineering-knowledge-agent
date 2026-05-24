#!/usr/bin/env python3
"""CLI entry point — runs the agent loop and prints the answer."""

import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

load_dotenv()

from agent import run_agent

console = Console()


def main(question: str) -> None:
    console.print(f"\n[bold]Question:[/bold] {question}\n")
    console.print("[dim]Agent is thinking...[/dim]")

    try:
        answer, tools_used = run_agent(question)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    console.print(Panel(Markdown(answer), title="[bold cyan]Answer[/bold cyan]", border_style="cyan"))
    if tools_used:
        console.print(f"[dim]Tools used: {', '.join(tools_used)}[/dim]")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("Usage: python query.py \"<your question>\"")
        sys.exit(1)
    main(" ".join(sys.argv[1:]))

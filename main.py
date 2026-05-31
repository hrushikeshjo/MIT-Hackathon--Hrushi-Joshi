"""
main.py — CLI entrypoint for the Disaster Response MAS.

Usage:
    python main.py                        # runs with built-in demo scenario
    python main.py "your situation here"  # runs with custom input
    echo "report text" | python main.py  # piped input
"""

import asyncio
import json
import sys
from rich.console import Console
from rich.panel import Panel
from rich.json import JSON
from agents.orchestrator import Orchestrator

console = Console()

DEMO_SITUATION = """
SITUATION REPORT — Received 14:32 UTC
Type: Magnitude 6.4 earthquake
Location: Los Angeles County, CA — epicenter near Pasadena
Estimated affected population: 50,000
Confirmed: Multiple structural collapses in Pasadena and Arcadia districts
Confirmed: Gas leaks in at least 3 locations in the Pasadena district
Unconfirmed: Highway 210 bridge damage near Irwindale
Unconfirmed: Cedar fire sparked near Monrovia foothills
Reported: Approximately 200 people trapped in two collapsed apartment buildings
Medical: Huntington Hospital reports mass casualty protocol activated
LIFE SAFETY FLAG: ACTIVE — confirmed entrapments, active gas leaks, possible fire
"""


async def main():
    if len(sys.argv) > 1:
        situation = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        situation = sys.stdin.read()
    else:
        situation = DEMO_SITUATION

    console.print(Panel("[bold]Disaster Response MAS[/bold] — Starting pipeline", style="blue"))
    console.print("\n[dim]Situation report:[/dim]")
    console.print(Panel(situation.strip(), style="dim"))

    orc = Orchestrator()

    with console.status("[bold blue]Running agent DAG...[/bold blue]", spinner="dots"):
        report = await orc.run(situation)

    console.print("\n[bold green]Pipeline complete. Situation report:[/bold green]\n")
    console.print(JSON(json.dumps(report, indent=2)))

    # Life safety flags deserve extra prominence
    if report.get("life_safety_flags"):
        console.print(Panel(
            "\n".join(f"⚠️  {f}" for f in report["life_safety_flags"]),
            title="[bold red]LIFE SAFETY FLAGS[/bold red]",
            style="red",
        ))


if __name__ == "__main__":
    asyncio.run(main())

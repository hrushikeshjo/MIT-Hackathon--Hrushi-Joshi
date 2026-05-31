"""
main.py - CLI entrypoint for the Disaster Response MAS.

Usage:
    python main.py                        # runs with built-in demo scenario
    python main.py "your situation here"  # runs with custom input
    echo "report text" | python main.py   # piped input
"""

import asyncio
import json
import sys

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

from agents.orchestrator import Orchestrator


console = Console()

DEMO_SITUATION = """
SITUATION REPORT - Received 14:32 UTC
Type: Magnitude 6.4 earthquake
Location: Los Angeles County, CA - epicenter near Pasadena
Estimated affected population: 50,000
Confirmed: Multiple structural collapses in Pasadena and Arcadia districts
Confirmed: Gas leaks in at least 3 locations in the Pasadena district
Unconfirmed: Highway 210 bridge damage near Irwindale
Unconfirmed: Cedar fire sparked near Monrovia foothills
Reported: Approximately 200 people trapped in two collapsed apartment buildings
Medical: Huntington Hospital reports mass casualty protocol activated
LIFE SAFETY FLAG: ACTIVE - confirmed entrapments, active gas leaks, possible fire
"""

DEMO_SITUATIONS = [
    {
        "id": "earthquake-pasadena",
        "name": "Earthquake - Pasadena",
        "situation": DEMO_SITUATION.strip(),
    },
    {
        "id": "wildfire-sonoma",
        "name": "Wildfire - Sonoma County",
        "situation": """
SITUATION REPORT - Received 16:05 UTC
Type: Wind-driven wildfire
Location: Sonoma County, CA - northeast of Santa Rosa
Estimated affected population: 18,000
Confirmed: Fast-moving fire front near two residential zones
Confirmed: Heavy smoke reducing visibility on evacuation corridors
Unconfirmed: Power line failure near Mark West Springs Road
Unconfirmed: Two assisted-living facilities may need evacuation support
Reported: Approximately 75 residents sheltering in place without transport
Medical: Local clinics report smoke exposure and respiratory distress cases
LIFE SAFETY FLAG: ACTIVE - evacuation support needed, smoke exposure, possible structure loss
""".strip(),
    },
    {
        "id": "flood-houston",
        "name": "Flooding - Houston",
        "situation": """
SITUATION REPORT - Received 09:40 UTC
Type: Flash flooding after severe thunderstorms
Location: Harris County, TX - southwest Houston
Estimated affected population: 32,000
Confirmed: Multiple low-water crossings submerged
Confirmed: Apartment complex ground floors taking water
Unconfirmed: Bayou levee overtopping near Brays Bayou
Unconfirmed: Backup generator failure at a senior housing facility
Reported: Approximately 120 people trapped above floodwater
Medical: EMS reports delayed access to dialysis and oxygen-dependent patients
LIFE SAFETY FLAG: ACTIVE - water rescues, vulnerable residents, blocked road access
""".strip(),
    },
    {
        "id": "tornado-nashville",
        "name": "Tornado - Nashville",
        "situation": """
SITUATION REPORT - Received 22:18 UTC
Type: Tornado impact with severe wind damage
Location: Davidson County, TN - east Nashville
Estimated affected population: 12,500
Confirmed: Roof collapse at a school gymnasium used as a community shelter
Confirmed: Downed power lines across several arterial roads
Unconfirmed: Natural gas odor reported near a damaged commercial block
Unconfirmed: Cellular service outage in two neighborhoods
Reported: Approximately 40 people trapped or unable to self-evacuate
Medical: Regional hospital requests patient distribution support
LIFE SAFETY FLAG: ACTIVE - collapse rescue, downed utilities, possible gas leak
""".strip(),
    },
    {
        "id": "chemical-newark",
        "name": "Chemical Spill - Newark",
        "situation": """
SITUATION REPORT - Received 03:25 UTC
Type: Hazardous materials release
Location: Newark, NJ - industrial corridor near Port Newark
Estimated affected population: 8,000
Confirmed: Chemical spill with vapor cloud inside a warehouse district
Confirmed: Shelter-in-place order requested for adjacent neighborhoods
Unconfirmed: Storm drain contamination near a rail spur
Unconfirmed: Two warehouse workers missing after alarm activation
Reported: Approximately 30 people exposed to respiratory irritants
Medical: Emergency department requests decontamination corridor support
LIFE SAFETY FLAG: ACTIVE - vapor exposure, missing workers, contamination risk
""".strip(),
    },
]


async def main() -> None:
    if len(sys.argv) > 1:
        situation = " ".join(sys.argv[1:])
    elif not sys.stdin.isatty():
        situation = sys.stdin.read()
    else:
        situation = DEMO_SITUATION

    console.print(Panel("[bold]Disaster Response MAS[/bold] - Starting pipeline", style="blue"))
    console.print("\n[dim]Situation report:[/dim]")
    console.print(Panel(situation.strip(), style="dim"))

    orchestrator = Orchestrator()

    with console.status("[bold blue]Running agent DAG...[/bold blue]", spinner="dots"):
        report = await orchestrator.run(situation)

    console.print("\n[bold green]Pipeline complete. Situation report:[/bold green]\n")
    console.print(JSON(json.dumps(report, indent=2)))

    if report.get("life_safety_flags"):
        console.print(
            Panel(
                "\n".join(f"!  {flag}" for flag in report["life_safety_flags"]),
                title="[bold red]LIFE SAFETY FLAGS[/bold red]",
                style="red",
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

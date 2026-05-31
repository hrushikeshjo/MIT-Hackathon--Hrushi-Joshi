# Disaster Response Multi-Agent System

A multi-agent LLM system for real-time disaster response coordination. Built on the Orchestrator + Specialist Agents pattern using the Anthropic API with web search.

## Architecture

```
User / Situation Report
        │
        ▼
  ┌─────────────┐
  │ Orchestrator│  ← parses intent, builds DAG, synthesizes final report
  └──────┬──────┘
         │  parallel (wave 1)
    ┌────┴────┐
    ▼         ▼
DataAggregator  ResourceMapper
    │         │
    └────┬────┘
         │  feeds into (wave 2)
    ┌────┴──────────┐
    ▼               ▼
TriageAgent    (waits for wave 1)
    │
    │  parallel (wave 3)
    ├──────────────┐
    ▼              ▼
CommunicationAgent  LogisticsAgent
    │              │
    └──────┬───────┘
           ▼
    Orchestrator synthesizes
           ▼
    Final Situation Report
```

## Agents

| Agent | Role | Wave |
|---|---|---|
| `DataAggregator` | Web search for live weather, news, social signals, official feeds | 1 |
| `ResourceMapper` | Identify shelters, hospitals, emergency units in affected area | 1 |
| `TriageAgent` | Score and rank needs by severity × urgency | 2 |
| `CommunicationAgent` | Draft public alerts, responder briefs, media statements | 3 |
| `LogisticsAgent` | Routing, deployments, supply chain, evacuation paths | 3 |

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/disaster-response-mas
cd disaster-response-mas
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
python main.py
```

## Usage

```python
from core.orchestrator import Orchestrator

orc = Orchestrator()
report = await orc.run("""
    SITUATION REPORT — 14:32 UTC
    Magnitude 6.4 earthquake, Los Angeles County.
    Estimated 50,000 affected. Multiple structure collapses reported.
    Gas leaks confirmed in Pasadena district. Life-safety flag: ACTIVE.
""")
print(report)
```

## Configuration

Edit `core/config.py` to adjust:
- `MAX_RETRIES` — per-agent retry budget (default: 2)
- `AGENT_TIMEOUT_SECONDS` — per-agent timeout (default: 30)
- `CONFIDENCE_THRESHOLD` — minimum confidence to accept result (default: 0.6)
- `ENABLE_CRITIC_LOOP` — self-correction pass on final synthesis (default: True)

## Design Decisions

- **DAG execution**: Wave 1 agents run in parallel. Wave 2 waits on Wave 1. Wave 3 runs in parallel after Wave 2. Total latency ≈ 3 × slowest_agent rather than sum of all agents.
- **Read-only tool access**: Agents only use web search. No write actions, no API side-effects.
- **Self-correction**: Orchestrator runs a critic pass on the synthesized report before returning. If confidence < threshold, it re-prompts the Generator with the critique inline.
- **Graceful degradation**: If an agent fails after retries, the Orchestrator flags the gap and proceeds with available data. A missing agent never crashes the pipeline.

## Tech Stack

- `anthropic` — API client with web search tool
- `asyncio` — DAG parallel execution
- `pydantic` — message schema validation
- `rich` — console output for local dev

## Project Structure

```
disaster-response-mas/
├── agents/
│   ├── base_agent.py           # Abstract base with retry + timeout logic
│   ├── orchestrator.py
│   ├── data_aggregator.py
│   ├── resource_mapper.py
│   ├── triage_agent.py
│   ├── communication_agent.py
│   └── logistics_agent.py
├── core/
│   ├── config.py
│   ├── dag_runner.py           # Parallel wave executor
│   ├── message_schema.py       # Pydantic task/result models
│   └── critic.py               # Self-correction loop
├── prompts/
│   └── system_prompts.py       # All agent system prompts as constants
├── ui/
│   └── dashboard.html          # Live web dashboard
├── tests/
│   └── test_pipeline.py
├── main.py
└── requirements.txt
```

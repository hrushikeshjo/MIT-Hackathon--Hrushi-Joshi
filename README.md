# Disaster Response Multi-Agent System

A local-ready multi-agent application for turning disaster situation reports into an incident summary, response priorities, life-safety flags, public alerts, resource gaps, and logistics recommendations.

The app keeps the original Orchestrator + Specialist Agents shape, but it now runs without an API key by using deterministic local analysis. If `ANTHROPIC_API_KEY` is present, agents can use the Anthropic API path; if it is absent, they automatically fall back to local mode.

## Run The Dashboard

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

The dashboard lets you paste a situation report, run the agent DAG, and inspect the generated plan.

## Run The CLI

```bash
python main.py
python main.py "Magnitude 6.4 earthquake near Pasadena with gas leaks and trapped residents"
```

You can also pipe a report:

```bash
type report.txt | python main.py
```

## Modes

By default the application uses `auto` mode:

- If `ANTHROPIC_API_KEY` is set, agents attempt the LLM/web-search path.
- If no API key is set, agents use the local deterministic engine.
- If an LLM call fails after retries, the agent returns a partial local fallback instead of crashing the pipeline.

Force local mode:

```bash
set DISASTER_MAS_MODE=local
python app.py
```

Force LLM mode:

```bash
set ANTHROPIC_API_KEY=your_key_here
set DISASTER_MAS_MODE=llm
python app.py
```

## Agents

| Agent | Role | Wave |
|---|---|---|
| `DataAggregator` | Extracts and summarizes incident facts and data gaps | 1 |
| `ResourceMapper` | Identifies resource types, likely constraints, and confirmation gaps | 1 |
| `TriageAgent` | Scores and ranks needs by severity x urgency | 2 |
| `CommunicationAgent` | Drafts public alerts, responder briefs, and media statements | 3 |
| `LogisticsAgent` | Recommends deployments, supply needs, routes, and chokepoints | 3 |

## Architecture

```text
Situation Report
      |
      v
Orchestrator
      |
      +-- Wave 1: DataAggregator + ResourceMapper
      |
      +-- Wave 2: TriageAgent
      |
      +-- Wave 3: CommunicationAgent + LogisticsAgent
      |
      v
Synthesized Situation Report
```

## Tests

```bash
pytest tests/
```

## Project Structure

```text
disaster-response-mas/
|-- agents/
|   |-- base_agent.py
|   |-- orchestrator.py
|   `-- specialists.py
|-- core/
|   |-- config.py
|   |-- dag_runner.py
|   |-- local_analysis.py
|   |-- message_schema.py
|   `-- critic.py
|-- prompts/
|   `-- system_prompts.py
|-- ui/
|   `-- dashboard.html
|-- tests/
|   `-- test_pipeline.py
|-- app.py
|-- main.py
`-- requirements.txt
```

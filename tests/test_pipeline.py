"""
Tests for the DAG runner and message schemas.
Run with: pytest tests/
"""

import asyncio
from core.message_schema import TaskMessage, ResultMessage
from core.dag_runner import run_wave, run_dag
from core.local_analysis import issue_catalog
from core.web_data import web_context_block
import core.config as config
import agents.orchestrator as orchestrator_module
from agents.orchestrator import Orchestrator


# --- Helpers ---

async def fast_agent(task: TaskMessage) -> ResultMessage:
    return ResultMessage(
        task_id=task.task_id,
        agent=task.agent,
        status="success",
        confidence="high",
        data={"result": f"output from {task.agent}"},
    )


async def slow_agent(task: TaskMessage) -> ResultMessage:
    await asyncio.sleep(2)
    return ResultMessage(
        task_id=task.task_id,
        agent=task.agent,
        status="success",
        confidence="medium",
        data={"result": "slow"},
    )


async def failing_agent(task: TaskMessage) -> ResultMessage:
    raise ValueError("Simulated agent failure")


# --- Tests ---

def test_task_message_defaults():
    t = TaskMessage(agent="TestAgent", task="do something", context="ctx")
    assert t.priority == "normal"
    assert t.retry_count == 0
    assert t.task_id is not None


def test_result_message():
    r = ResultMessage(task_id="abc", agent="A", status="success", confidence="high")
    assert r.errors == []
    assert r.timestamp is not None


def test_run_wave_parallel():
    async def scenario():
        tasks = [
            ("A", fast_agent, TaskMessage(agent="A", task="t", context="c")),
            ("B", fast_agent, TaskMessage(agent="B", task="t", context="c")),
        ]
        return await run_wave(tasks)

    results = asyncio.run(scenario())
    assert results["A"].status == "success"
    assert results["B"].status == "success"


def test_run_wave_timeout():
    async def scenario():
        tasks = [
            ("Slow", slow_agent, TaskMessage(agent="Slow", task="t", context="c")),
        ]
        return await run_wave(tasks, timeout=1)

    results = asyncio.run(scenario())
    assert results["Slow"].status == "error"
    assert "timed out" in results["Slow"].errors[0]


def test_run_wave_failure_handled():
    async def scenario():
        tasks = [
            ("Fail", failing_agent, TaskMessage(agent="Fail", task="t", context="c")),
        ]
        return await run_wave(tasks)

    results = asyncio.run(scenario())
    assert results["Fail"].status == "error"


def test_run_dag_three_waves():
    async def scenario():
        w1 = [
            ("A", fast_agent, TaskMessage(agent="A", task="t", context="c")),
            ("B", fast_agent, TaskMessage(agent="B", task="t", context="c")),
        ]

        def w2_builder(prior):
            t = TaskMessage(agent="C", task="t", context=str(prior))
            return [("C", fast_agent, t)]

        def w3_builder(prior):
            t1 = TaskMessage(agent="D", task="t", context=str(prior))
            t2 = TaskMessage(agent="E", task="t", context=str(prior))
            return [("D", fast_agent, t1), ("E", fast_agent, t2)]

        return await run_dag(w1, w2_builder, w3_builder)

    results = asyncio.run(scenario())
    assert set(results.keys()) == {"A", "B", "C", "D", "E"}
    assert all(r.status == "success" for r in results.values())


def test_orchestrator_local_pipeline_generates_action_plan(monkeypatch):
    monkeypatch.setattr(config, "RUN_MODE", "local")
    monkeypatch.setattr(
        orchestrator_module,
        "collect_web_data",
        lambda _: {
            "findings": [
                {
                    "source": "National Weather Service",
                    "category": "weather",
                    "finding": "Test weather alert.",
                    "confidence": "verified",
                    "url": "https://api.weather.gov/alerts/active",
                }
            ],
            "summary": "Test web summary.",
            "errors": [],
        },
    )

    async def scenario():
        return await Orchestrator().run(
            """
            SITUATION REPORT
            Type: Magnitude 6.4 earthquake
            Location: Los Angeles County, CA
            Estimated affected population: 50,000
            Confirmed: Multiple structural collapses and gas leaks.
            Reported: Approximately 200 people trapped.
            LIFE SAFETY FLAG: ACTIVE
            """
        )

    report = asyncio.run(scenario())

    assert report["top_priorities"]
    assert report["life_safety_flags"]
    assert report["resource_status"]["overall"] == "critical"
    assert report["issue_catalog"]
    assert report["issue_summary"]["total_active_issues"] >= 1
    assert any(issue["category"] == "hazmat" for issue in report["issue_catalog"])
    assert report["web_data"]["findings"]
    assert report["logistics_recommendations"]["deployments"]
    assert set(report["agent_statuses"].keys()) == {
        "DataAggregator",
        "ResourceMapper",
        "TriageAgent",
        "CommunicationAgent",
        "LogisticsAgent",
    }


def test_issue_catalog_extracts_multiple_current_instances():
    issues = issue_catalog(
        """
        SITUATION REPORT
        Location: Harris County, TX - southwest Houston
        Confirmed: Multiple low-water crossings submerged.
        Unconfirmed: Bayou levee overtopping near Brays Bayou.
        Reported: Approximately 120 people trapped above floodwater.
        Medical: EMS reports delayed access to dialysis and oxygen-dependent patients.
        LIFE SAFETY FLAG: ACTIVE
        """
    )

    categories = {issue["category"] for issue in issues}
    assert {"life_safety", "transportation", "medical", "weather"}.issubset(categories)
    assert issues[0]["priority_score"] >= issues[-1]["priority_score"]
    assert any(issue["status"] == "needs_confirmation" for issue in issues)


def test_web_context_block_serializes_findings():
    block = web_context_block(
        {
            "findings": [{"source": "USGS", "finding": "Magnitude 4.5 earthquake reported."}],
            "errors": [],
        }
    )

    assert "WEB DATA CONTEXT" in block
    assert "USGS" in block

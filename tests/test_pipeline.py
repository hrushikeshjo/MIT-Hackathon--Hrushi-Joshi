"""
Tests for the DAG runner and message schemas.
Run with: pytest tests/
"""

import asyncio
import pytest
from core.message_schema import TaskMessage, ResultMessage
from core.dag_runner import run_wave, run_dag


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


@pytest.mark.asyncio
async def test_run_wave_parallel():
    tasks = [
        ("A", fast_agent, TaskMessage(agent="A", task="t", context="c")),
        ("B", fast_agent, TaskMessage(agent="B", task="t", context="c")),
    ]
    results = await run_wave(tasks)
    assert results["A"].status == "success"
    assert results["B"].status == "success"


@pytest.mark.asyncio
async def test_run_wave_timeout():
    tasks = [
        ("Slow", slow_agent, TaskMessage(agent="Slow", task="t", context="c")),
    ]
    results = await run_wave(tasks, timeout=1)
    assert results["Slow"].status == "error"
    assert "timed out" in results["Slow"].errors[0]


@pytest.mark.asyncio
async def test_run_wave_failure_handled():
    tasks = [
        ("Fail", failing_agent, TaskMessage(agent="Fail", task="t", context="c")),
    ]
    results = await run_wave(tasks)
    assert results["Fail"].status == "error"


@pytest.mark.asyncio
async def test_run_dag_three_waves():
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

    results = await run_dag(w1, w2_builder, w3_builder)
    assert set(results.keys()) == {"A", "B", "C", "D", "E"}
    assert all(r.status == "success" for r in results.values())

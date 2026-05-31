"""
DAG Runner — executes agents in dependency-ordered waves.

Wave 1 (parallel): DataAggregator, ResourceMapper
Wave 2 (serial):   TriageAgent         ← needs Wave 1 outputs
Wave 3 (parallel): CommunicationAgent, LogisticsAgent  ← needs Wave 2
"""

import asyncio
from typing import Callable, Dict, List, Any
from core.message_schema import TaskMessage, ResultMessage


async def run_wave(
    agents: List[tuple[str, Callable, TaskMessage]],
    timeout: int = 30,
) -> Dict[str, ResultMessage]:
    """Run a list of (name, coro_fn, task) tuples in parallel with timeout."""

    async def run_one(name: str, fn: Callable, task: TaskMessage) -> tuple[str, ResultMessage]:
        try:
            result = await asyncio.wait_for(fn(task), timeout=timeout)
            return name, result
        except asyncio.TimeoutError:
            return name, ResultMessage(
                task_id=task.task_id,
                agent=name,
                status="error",
                confidence="low",
                errors=[f"Agent timed out after {timeout}s"],
            )
        except Exception as e:
            return name, ResultMessage(
                task_id=task.task_id,
                agent=name,
                status="error",
                confidence="low",
                errors=[str(e)],
            )

    results = await asyncio.gather(*[run_one(n, fn, t) for n, fn, t in agents])
    return dict(results)


async def run_dag(
    wave1_agents: List[tuple[str, Callable, TaskMessage]],
    wave2_builder: Callable[[Dict[str, ResultMessage]], List[tuple[str, Callable, TaskMessage]]],
    wave3_builder: Callable[[Dict[str, ResultMessage]], List[tuple[str, Callable, TaskMessage]]],
    timeout: int = 30,
) -> Dict[str, ResultMessage]:
    """
    Execute the 3-wave DAG.
    wave2_builder and wave3_builder receive prior results to build their task lists.
    """
    all_results: Dict[str, ResultMessage] = {}

    # Wave 1
    w1 = await run_wave(wave1_agents, timeout)
    all_results.update(w1)

    # Wave 2
    w2_agents = wave2_builder(all_results)
    w2 = await run_wave(w2_agents, timeout)
    all_results.update(w2)

    # Wave 3
    w3_agents = wave3_builder(all_results)
    w3 = await run_wave(w3_agents, timeout)
    all_results.update(w3)

    return all_results

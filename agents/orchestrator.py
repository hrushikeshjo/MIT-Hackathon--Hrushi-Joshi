"""
Orchestrator — coordinates the DAG, synthesizes the final report,
and runs the optional critic self-correction pass.
"""

import json
from typing import Dict, Any

from core.config import ENABLE_CRITIC_LOOP
from core.message_schema import TaskMessage, ResultMessage
from core.dag_runner import run_dag
from core.critic import critique_report
from core.local_analysis import extract_situation, issue_catalog, utc_now
from core.web_data import collect_web_data, web_context_block
from agents.specialists import (
    DataAggregatorAgent,
    ResourceMapperAgent,
    TriageAgent,
    CommunicationAgent,
    LogisticsAgent,
)


class Orchestrator:
    def __init__(self):
        self.data_agg = DataAggregatorAgent()
        self.resource_mapper = ResourceMapperAgent()
        self.triage = TriageAgent()
        self.comms = CommunicationAgent()
        self.logistics = LogisticsAgent()

    def _make_task(self, agent: str, task: str, context: str, priority: str = "high") -> TaskMessage:
        return TaskMessage(agent=agent, task=task, context=context, priority=priority)

    async def run(self, situation_report: str) -> Dict[str, Any]:
        """
        Main entry point. Takes a raw situation report string, runs the full
        DAG pipeline, and returns the synthesized situation report dict.
        """
        web_data = collect_web_data(situation_report)
        enriched_report = situation_report + web_context_block(web_data)

        # --- Wave 1 tasks (parallel) ---
        w1_data = self._make_task(
            "DataAggregator",
            f"Search for live data about this incident. Find weather, news, and official emergency feeds.",
            enriched_report,
            "critical",
        )
        w1_resources = self._make_task(
            "ResourceMapper",
            "Identify available shelters, hospitals, and emergency units in the affected area.",
            enriched_report,
            "critical",
        )

        # Wave 2 builder — uses Wave 1 outputs
        def wave2_builder(prior: Dict[str, ResultMessage]):
            data_summary = json.dumps(prior.get("DataAggregator", {}).data or {})
            resource_summary = json.dumps(prior.get("ResourceMapper", {}).data or {})
            context = f"DataAggregator output:\n{data_summary}\n\nResourceMapper output:\n{resource_summary}\n\nOriginal report:\n{enriched_report}"
            task = self._make_task(
                "TriageAgent",
                "Analyze all data and produce a ranked priority list of immediate needs.",
                context,
                "critical",
            )
            return [("TriageAgent", self.triage.run, task)]

        # Wave 3 builder — uses Wave 1 + 2 outputs
        def wave3_builder(prior: Dict[str, ResultMessage]):
            triage_summary = json.dumps(prior.get("TriageAgent", {}).data or {})
            resource_summary = json.dumps(prior.get("ResourceMapper", {}).data or {})

            comms_context = f"Triage priorities:\n{triage_summary}\n\nOriginal report:\n{enriched_report}"
            logistics_context = f"Resources:\n{resource_summary}\n\nTriage:\n{triage_summary}\n\nOriginal report:\n{enriched_report}"

            comms_task = self._make_task(
                "CommunicationAgent",
                "Draft public alerts, responder briefing, and media statement based on triage priorities.",
                comms_context,
                "high",
            )
            logistics_task = self._make_task(
                "LogisticsAgent",
                "Recommend resource deployments, routing, supply needs, and evacuation routes.",
                logistics_context,
                "high",
            )
            return [
                ("CommunicationAgent", self.comms.run, comms_task),
                ("LogisticsAgent", self.logistics.run, logistics_task),
            ]

        # --- Run the DAG ---
        all_results = await run_dag(
            wave1_agents=[
                ("DataAggregator", self.data_agg.run, w1_data),
                ("ResourceMapper", self.resource_mapper.run, w1_resources),
            ],
            wave2_builder=wave2_builder,
            wave3_builder=wave3_builder,
        )

        # --- Synthesize ---
        report = self._synthesize(situation_report, all_results, web_data)

        # --- Critic pass ---
        if ENABLE_CRITIC_LOOP:
            report = critique_report(report, situation_report)

        return report

    def _synthesize(
        self,
        situation_report: str,
        results: Dict[str, ResultMessage],
        web_data: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Merge all agent outputs into a unified situation report."""
        situation = extract_situation(situation_report)

        def safe_data(agent_name: str) -> dict:
            r = results.get(agent_name)
            if r and r.status != "error" and r.data:
                return r.data
            return {}

        triage = safe_data("TriageAgent")
        resources = safe_data("ResourceMapper")
        comms = safe_data("CommunicationAgent")
        logistics = safe_data("LogisticsAgent")
        data_agg = safe_data("DataAggregator")
        web_data = web_data or {}
        issues = triage.get("issue_catalog") or data_agg.get("issue_catalog") or issue_catalog(situation_report)

        # Determine overall confidence
        confidences = [r.confidence for r in results.values() if r.status == "success"]
        if "low" in confidences:
            overall = "low"
        elif confidences.count("high") >= 3:
            overall = "high"
        else:
            overall = "medium"

        # Collect open unknowns from all agents
        unknowns = []
        for agent_name, result in results.items():
            if result.status == "error":
                unknowns.append(f"{agent_name} failed: {'; '.join(result.errors)}")
        unknowns += data_agg.get("data_gaps", [])
        unknowns += resources.get("critical_gaps", [])

        hazards = ", ".join(h for h in situation["hazards"] if h != "unknown") or "incident"
        affected = ""
        if situation["affected_population"]:
            affected = f" Estimated affected population: {situation['affected_population']:,}."

        issue_counts: dict[str, int] = {}
        for issue in issues:
            category = issue.get("category", "uncategorized")
            issue_counts[category] = issue_counts.get(category, 0) + 1

        return {
            "incident_summary": (
                f"{hazards.title()} response in {situation['location']}.{affected} "
                f"{len(results)} specialist agents produced a coordinated local action plan."
            ),
            "top_priorities": triage.get("priorities", [])[:3],
            "issue_catalog": issues,
            "issue_summary": {
                "total_active_issues": len([issue for issue in issues if issue.get("status") == "active"]),
                "total_needs_confirmation": len([issue for issue in issues if issue.get("status") == "needs_confirmation"]),
                "by_category": issue_counts,
                "highest_priority_score": max([issue.get("priority_score", 0) for issue in issues], default=0),
            },
            "resource_status": {
                "overall": resources.get("overall_resource_status", "unknown"),
                "resources": resources.get("resources", []),
            },
            "active_alerts": comms.get("drafts", []),
            "logistics_recommendations": {
                "deployments": logistics.get("deployments", []),
                "supply_needs": logistics.get("supply_needs", []),
                "evacuation_routes": logistics.get("evacuation_routes", []),
                "bottlenecks": logistics.get("bottlenecks", []),
            },
            "data_confidence": data_agg.get("overall_confidence", "low"),
            "web_data": web_data,
            "open_unknowns": unknowns,
            "overall_confidence": overall,
            "life_safety_flags": triage.get("life_safety_flags", []),
            "agent_statuses": {
                name: {"status": r.status, "confidence": r.confidence}
                for name, r in results.items()
            },
            "generated_at": utc_now(),
        }

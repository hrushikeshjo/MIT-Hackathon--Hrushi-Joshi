from agents.base_agent import BaseAgent
from prompts.system_prompts import (
    DATA_AGGREGATOR_SYSTEM_PROMPT,
    RESOURCE_MAPPER_SYSTEM_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
    COMMUNICATION_SYSTEM_PROMPT,
    LOGISTICS_SYSTEM_PROMPT,
)


class DataAggregatorAgent(BaseAgent):
    agent_name = "DataAggregator"
    system_prompt = DATA_AGGREGATOR_SYSTEM_PROMPT


class ResourceMapperAgent(BaseAgent):
    agent_name = "ResourceMapper"
    system_prompt = RESOURCE_MAPPER_SYSTEM_PROMPT


class TriageAgent(BaseAgent):
    agent_name = "TriageAgent"
    system_prompt = TRIAGE_SYSTEM_PROMPT

    def _build_user_message(self, task):
        return f"""Task: {task.task}

Situation context: {task.context}

Priority: {task.priority}

Return valid JSON only. No markdown fences, no preamble."""


class CommunicationAgent(BaseAgent):
    agent_name = "CommunicationAgent"
    system_prompt = COMMUNICATION_SYSTEM_PROMPT


class LogisticsAgent(BaseAgent):
    agent_name = "LogisticsAgent"
    system_prompt = LOGISTICS_SYSTEM_PROMPT

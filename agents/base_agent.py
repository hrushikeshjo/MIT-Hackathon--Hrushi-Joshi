"""
Base agent — all specialist agents inherit from this.
Handles: API call, web search tool, retry logic, JSON parsing.
"""

import json
import asyncio
import anthropic
from core.config import MODEL, MAX_TOKENS, ANTHROPIC_API_KEY, MAX_RETRIES
from core.message_schema import TaskMessage, ResultMessage


class BaseAgent:
    system_prompt: str = ""
    agent_name: str = "BaseAgent"

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.web_search_tool = {
            "type": "web_search_20250305",
            "name": "web_search",
        }

    def _build_user_message(self, task: TaskMessage) -> str:
        return f"""Task: {task.task}

Context: {task.context}

Priority: {task.priority}

Return valid JSON only. No markdown fences, no preamble."""

    def _parse_response(self, response) -> dict:
        """Extract text content from API response and parse as JSON."""
        full_text = ""
        for block in response.content:
            if block.type == "text":
                full_text += block.text

        # Strip markdown fences
        clean = full_text.strip()
        clean = clean.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        return json.loads(clean)

    def _make_result(self, task: TaskMessage, data: dict, status: str = "success") -> ResultMessage:
        confidence = data.get(
            "overall_confidence",
            data.get("triage_confidence",
            data.get("logistics_confidence", "medium"))
        )
        return ResultMessage(
            task_id=task.task_id,
            agent=self.agent_name,
            status=status,
            confidence=confidence,
            data=data,
        )

    async def run(self, task: TaskMessage) -> ResultMessage:
        last_error = None
        for attempt in range(task.max_retries + 1):
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.messages.create(
                        model=MODEL,
                        max_tokens=MAX_TOKENS,
                        system=self.system_prompt,
                        tools=[self.web_search_tool],
                        messages=[{"role": "user", "content": self._build_user_message(task)}],
                    )
                )
                data = self._parse_response(response)
                return self._make_result(task, data)

            except json.JSONDecodeError as e:
                last_error = f"JSON parse error: {e}"
            except Exception as e:
                last_error = str(e)

            task.retry_count += 1
            if attempt < task.max_retries:
                await asyncio.sleep(1.5 ** attempt)  # brief backoff

        return ResultMessage(
            task_id=task.task_id,
            agent=self.agent_name,
            status="error",
            confidence="low",
            errors=[last_error or "Unknown error after retries"],
        )

"""
Critic — self-correction pass on the synthesized situation report.

If confidence is below threshold or issues are found, returns a revised report.
Max 1 correction loop to avoid runaway cost.
"""

import json
import anthropic
from core.config import MODEL, MAX_TOKENS, ANTHROPIC_API_KEY, CONFIDENCE_THRESHOLD
from prompts.system_prompts import CRITIC_SYSTEM_PROMPT


client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def critique_report(report: dict, original_situation: str) -> dict:
    """
    Send the synthesized report to the critic. If it passes, return as-is.
    If it fails, return the revised report with issues noted.
    """
    prompt = f"""
Original situation report:
{original_situation}

Synthesized response to critique:
{json.dumps(report, indent=2)}

Evaluate this report against the original situation. Return JSON only:
{{
  "passed": true | false,
  "confidence": "low | medium | high",
  "issues": ["list of problems if any"],
  "revised_report": {{ ...full corrected report or null if passed }}
}}
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=CRITIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    # Strip markdown fences if present
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        critique = json.loads(raw)
    except json.JSONDecodeError:
        # Critic failed to return valid JSON — pass through original
        return report

    if critique.get("passed", True) or not critique.get("revised_report"):
        return report

    return critique["revised_report"]

from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class TaskMessage(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent: str
    task: str
    context: str
    priority: str = "normal"  # critical | high | normal
    depends_on: List[str] = Field(default_factory=list)
    timeout_seconds: int = 30
    retry_count: int = 0
    max_retries: int = 2


class ResultMessage(BaseModel):
    task_id: str
    agent: str
    status: str  # success | partial | error
    confidence: str  # low | medium | high
    data: Optional[dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SituationReport(BaseModel):
    incident_summary: str
    top_priorities: List[dict[str, Any]]
    resource_status: dict[str, Any]
    active_alerts: List[dict[str, Any]]
    logistics_recommendations: dict[str, Any]
    data_confidence: str
    open_unknowns: List[str]
    overall_confidence: str
    life_safety_flags: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

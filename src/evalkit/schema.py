"""Core data model.

Evaluation targets a trace, not just a final string. A case can assert that a
tool was called, in what order, at what cost -- things a text diff cannot see.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    type: str
    name: str | None = None
    ts_ms: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    output: str = ""
    trace: list[TraceEvent] = Field(default_factory=list)
    cost_usd: float = 0.0
    # Where the money figure came from. "simulated" means the number is a
    # placeholder for exercise purposes and MUST NOT be read as spend.
    cost_source: Literal["actual", "simulated", "none"] = "none"
    latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def tools(self) -> list[str]:
        return [e.name for e in self.trace if e.type in {"tool_call", "tool"} and e.name]


class Case(BaseModel):
    id: str
    input: str
    repeat: int = 1
    tags: list[str] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)


class AssertionResult(BaseModel):
    type: str
    passed: bool
    detail: str = ""


class CaseResult(BaseModel):
    case_id: str
    run: int
    passed: bool
    assertions: list[AssertionResult] = Field(default_factory=list)
    cost_usd: float = 0.0
    cost_source: str = "none"
    latency_ms: float = 0.0
    output_digest: str = ""

    @staticmethod
    def digest_output(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class CaseSummary(BaseModel):
    case_id: str
    runs: int
    passes: int
    pass_rate: float
    flaky: bool
    mean_cost_usd: float
    mean_latency_ms: float
    failures: list[str] = Field(default_factory=list)


class Report(BaseModel):
    suite: str
    started_at: str
    finished_at: str
    adapter: str
    results: list[CaseResult] = Field(default_factory=list)
    summaries: list[CaseSummary] = Field(default_factory=list)
    pass_rate: float = 0.0
    pass_ci: tuple[float, float] = (0.0, 0.0)
    total_cost_usd: float = 0.0
    cost_basis: str = "none"
    mean_latency_ms: float = 0.0
    flaky_cases: int = 0

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.model_dump_json())


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

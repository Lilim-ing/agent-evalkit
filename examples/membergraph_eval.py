"""Dogfooding adapter: evaluate the membergraph repo with evalkit.

This is the cross-repo example referenced in the plan. It imports membergraph
from a sibling directory -- both repos must be checked out side by side.

    agent-portfolio/
    ├── membergraph/
    └── agent-evalkit/   <- you are here
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "membergraph" / "src"))

MEMBERGRAPH = ROOT / "membergraph"

_IMPORT_ERROR: Exception | None = None
try:
    from membergraph.orchestrator import Orchestrator, RunConfig  # noqa: E402
except Exception as exc:  # noqa: BLE001 - surfaced per case instead of crashing the suite
    _IMPORT_ERROR = exc
    Orchestrator = None  # type: ignore[assignment]
    RunConfig = None  # type: ignore[assignment]


def agent(question: str) -> dict:
    if _IMPORT_ERROR is not None:
        raise RuntimeError(
            "跨仓库示例需要先安装 membergraph 及其依赖：pip install -e ../membergraph"
            f"（原始错误：{type(_IMPORT_ERROR).__name__}: {_IMPORT_ERROR}）"
        )
    out_dir = Path(tempfile.mkdtemp(prefix="mg-eval-"))
    plan = Orchestrator(MEMBERGRAPH / "data" / "fixtures", RunConfig(topic=question, out_dir=out_dir)).run()

    events = [
        json.loads(line)
        for line in (out_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    trace = [
        {"type": "tool_call", "name": e.get("tool")} for e in events if e.get("type") == "tool_call"
    ]

    first_metric = next((e for e in plan.evidence if e.kind == "metric"), None)
    payload = {
        "claims": [c.model_dump() for c in plan.claims],
        "evidence_ids": [e.id for e in plan.evidence],
        "kpi": {"value": first_metric.value if first_metric else None},
        "actions": [a.model_dump() for a in plan.actions],
        "degraded": plan.degraded,
    }
    return {
        "output": json.dumps(payload, ensure_ascii=False),
        "trace": trace,
        "cost_usd": plan.budget.get("spent_usd", 0.0),
        "cost_source": "simulated",
        "latency_ms": plan.budget.get("elapsed_ms", 0.0),
        "metadata": {"run_id": plan.run_id},
    }


def has_actions(response) -> tuple[bool, str]:
    try:
        data = json.loads(response.output)
    except json.JSONDecodeError:
        return False, "output is not JSON"
    actions = data.get("actions") or []
    complete = all(a.get("success_metric") and a.get("segment") for a in actions)
    return bool(actions) and complete, f"actions={len(actions)}, complete={complete}"


def not_degraded(response) -> tuple[bool, str]:
    data = json.loads(response.output)
    return not data.get("degraded", False), f"degraded={data.get('degraded')}"

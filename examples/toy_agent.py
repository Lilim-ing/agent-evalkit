"""A deterministic toy agent used by the bundled suite.

It exists to demonstrate three things the framework must handle: a well-grounded
answer, an answer with a claim that is not backed by evidence, and a genuinely
unstable answer that alternates between pass and fail.
"""

from __future__ import annotations

import json
from typing import Any

_FLAKY_COUNTER = {"n": 0}


def _payload(claims: list[dict], evidence: list[str], kpi: dict[str, float]) -> str:
    return json.dumps(
        {"claims": claims, "evidence_ids": evidence, "kpi": kpi},
        ensure_ascii=False,
    )


def agent(text: str) -> dict[str, Any]:
    if "炸" in text:
        raise RuntimeError("simulated adapter failure")

    if "flaky" in text:
        _FLAKY_COUNTER["n"] += 1
        unstable = _FLAKY_COUNTER["n"] % 2 == 1
        return {
            "output": _payload(
                [{"id": "c1", "text": "复购率小幅下滑", "evidence_ids": ["e1"]}],
                ["e1"],
                {"repurchase_rate": 0.131},
            ),
            "trace": (
                [{"type": "tool_call", "name": "query_cohort"}]
                if unstable
                else [{"type": "tool_call", "name": "query_other"}]
            ),
            "cost_usd": 0.003,
            "cost_source": "simulated",
            "latency_ms": 640,
        }

    if "缺少证据" in text:
        return {
            "output": _payload(
                [
                    {"id": "c1", "text": "复购率下滑", "evidence_ids": ["e1"]},
                    {"id": "c2", "text": "因为竞品降价", "evidence_ids": []},
                ],
                ["e1"],
                {"repurchase_rate": 0.128},
            ),
            "trace": [{"type": "tool_call", "name": "query_cohort"}],
            "cost_usd": 0.004,
            "cost_source": "simulated",
            "latency_ms": 800,
        }

    if "流失" in text or "沉睡" in text:
        return {
            "output": _payload(
                [
                    {"id": "c1", "text": "180 天沉睡会员占比上升至 18.2%", "evidence_ids": ["e1"]},
                    {"id": "c2", "text": "集中在银卡与普通会员", "evidence_ids": ["e1", "e2"]},
                ],
                ["e1", "e2"],
                {"churn_rate": 0.182},
            ),
            "trace": [
                {"type": "tool_call", "name": "query_cohort"},
                {"type": "tool_call", "name": "decompose_metric"},
            ],
            "cost_usd": 0.005,
            "cost_source": "simulated",
            "latency_ms": 910,
        }

    if "客单" in text or "连带" in text:
        return {
            "output": _payload(
                [
                    {"id": "c1", "text": "客单价 287 元，连带率 1.42 件/单", "evidence_ids": ["e1"]},
                    {"id": "c2", "text": "连带率下降主要来自文胸品类", "evidence_ids": ["e2"]},
                ],
                ["e1", "e2"],
                {"aov": 287.0, "upt": 1.42},
            ),
            "trace": [
                {"type": "tool_call", "name": "query_metric"},
                {"type": "tool_call", "name": "decompose_metric"},
            ],
            "cost_usd": 0.004,
            "cost_source": "simulated",
            "latency_ms": 760,
        }

    return {
        "output": _payload(
            [
                {"id": "c1", "text": "90 天复购率 13.1%，环比下降 1.9pct", "evidence_ids": ["e1"]},
                {"id": "c2", "text": "小程序渠道降幅最大（-2.9pct）", "evidence_ids": ["e1", "e2"]},
            ],
            ["e1", "e2"],
            {"repurchase_rate": 0.131},
        ),
        "trace": [
            {"type": "tool_call", "name": "query_cohort"},
            {"type": "tool_call", "name": "decompose_metric"},
        ],
        "cost_usd": 0.004,
        "cost_source": "simulated",
        "latency_ms": 820,
    }


def has_two_claims(response) -> tuple[bool, str]:
    """Custom assertion example: parse the output and count claims."""
    try:
        data = json.loads(response.output)
    except json.JSONDecodeError:
        return False, "output is not JSON"
    count = len(data.get("claims") or [])
    return count >= 2, f"claims={count}"

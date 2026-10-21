"""Assertion registry.

Assertions run against the whole AgentResponse (output + trace + cost), which is
what makes it possible to check *how* an answer was produced, not only what it
says.
"""

from __future__ import annotations

import importlib
import json
import re
from typing import Any, Callable

from .schema import AgentResponse, AssertionResult

REGISTRY: dict[str, Callable[[AgentResponse, dict[str, Any]], AssertionResult]] = {}

_judge: Callable[[str, str], int] | None = None


def register(name: str):
    def decorator(fn):
        REGISTRY[name] = fn
        return fn

    return decorator


def set_judge(fn: Callable[[str, str], int] | None) -> None:
    global _judge
    _judge = fn


def default_judge(output: str, rubric: str) -> int:
    """Deterministic placeholder judge.

    It is a heuristic, not a model. The point of shipping it is to make the
    calibration workflow runnable offline; swapping in a real judge is one
    function argument. `docs/JUDGE_CALIBRATION.md` explains why an uncalibrated
    judge must not gate CI.
    """
    score = 2
    if len(output) >= 40:
        score += 1
    if re.search(r"\d", output):
        score += 1
    if rubric == "actionability" and re.search(r"(投放|触达|预算|人群|渠道|指标)", output):
        score += 1
    return max(1, min(5, score))


def _ok(kind: str, passed: bool, detail: str = "") -> AssertionResult:
    return AssertionResult(type=kind, passed=passed, detail=detail)


def _json_output(resp: AgentResponse) -> dict[str, Any] | None:
    try:
        value = json.loads(resp.output)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _dig(obj: Any, path: str) -> Any:
    if not path or path == "$":
        return obj
    node = obj
    for part in path.lstrip("$").lstrip(".").split("."):
        if not part:
            continue
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return node


@register("contains")
def _contains(resp: AgentResponse, spec: dict) -> AssertionResult:
    value = str(spec["value"])
    return _ok("contains", value in resp.output, f"looking for {value[:40]!r}")


@register("not_contains")
def _not_contains(resp: AgentResponse, spec: dict) -> AssertionResult:
    value = str(spec["value"])
    return _ok("not_contains", value not in resp.output, f"forbidden {value[:40]!r}")


@register("regex")
def _regex(resp: AgentResponse, spec: dict) -> AssertionResult:
    pattern = re.compile(str(spec["pattern"]))
    match = pattern.search(resp.output)
    return _ok("regex", bool(match), f"pattern {pattern.pattern!r}")


@register("json_has")
def _json_has(resp: AgentResponse, spec: dict) -> AssertionResult:
    data = _json_output(resp)
    if data is None:
        return _ok("json_has", False, "output is not a JSON object")
    missing = [k for k in spec.get("keys", []) if k not in data]
    return _ok("json_has", not missing, f"missing keys: {missing}")


@register("numeric_close")
def _numeric_close(resp: AgentResponse, spec: dict) -> AssertionResult:
    data = _json_output(resp)
    if data is None:
        return _ok("numeric_close", False, "output is not a JSON object")
    actual = _dig(data, spec.get("path", ""))
    try:
        actual_f = float(actual)
    except (TypeError, ValueError):
        return _ok("numeric_close", False, f"value at {spec.get('path')} is not numeric: {actual!r}")
    expected = float(spec["value"])
    tol = float(spec.get("tol", 1e-6))
    return _ok("numeric_close", abs(actual_f - expected) <= tol, f"{actual_f} vs {expected} ±{tol}")


@register("tool_called")
def _tool_called(resp: AgentResponse, spec: dict) -> AssertionResult:
    tool = str(spec["tool"])
    return _ok("tool_called", tool in resp.tools(), f"tools used: {resp.tools()}")


@register("tool_not_called")
def _tool_not_called(resp: AgentResponse, spec: dict) -> AssertionResult:
    tool = str(spec["tool"])
    return _ok("tool_not_called", tool not in resp.tools(), f"tools used: {resp.tools()}")


@register("tool_order")
def _tool_order(resp: AgentResponse, spec: dict) -> AssertionResult:
    expected = [str(t) for t in spec["tools"]]
    used = resp.tools()
    index = 0
    for tool in used:
        if index < len(expected) and tool == expected[index]:
            index += 1
    return _ok("tool_order", index == len(expected), f"expected {expected}, got {used}")


@register("max_cost")
def _max_cost(resp: AgentResponse, spec: dict) -> AssertionResult:
    limit = float(spec["value"])
    return _ok("max_cost", resp.cost_usd <= limit, f"${resp.cost_usd:.6f} <= ${limit}")


@register("max_latency_ms")
def _max_latency_ms(resp: AgentResponse, spec: dict) -> AssertionResult:
    limit = float(spec["value"])
    return _ok("max_latency_ms", resp.latency_ms <= limit, f"{resp.latency_ms:.0f}ms <= {limit:.0f}ms")


@register("evidence_coverage")
def _evidence_coverage(resp: AgentResponse, spec: dict) -> AssertionResult:
    data = _json_output(resp)
    claims = (data or {}).get("claims") or []
    if not claims:
        return _ok("evidence_coverage", False, "no claims in output")
    covered = sum(1 for c in claims if c.get("evidence_ids"))
    ratio = covered / len(claims)
    minimum = float(spec.get("min", 0.9))
    return _ok("evidence_coverage", ratio >= minimum, f"{covered}/{len(claims)} = {ratio:.2f}")


@register("no_orphan_claims")
def _no_orphan_claims(resp: AgentResponse, spec: dict) -> AssertionResult:
    data = _json_output(resp)
    if not data:
        return _ok("no_orphan_claims", False, "output is not a JSON object")
    known = set(data.get("evidence_ids") or [])
    orphans = [
        c.get("id")
        for c in (data.get("claims") or [])
        if not c.get("evidence_ids") or not set(c.get("evidence_ids") or []) <= known
    ]
    return _ok("no_orphan_claims", not orphans, f"orphans: {orphans}")


@register("llm_judge")
def _llm_judge(resp: AgentResponse, spec: dict) -> AssertionResult:
    judge = _judge or default_judge
    rubric = str(spec.get("rubric", "quality"))
    score = int(judge(resp.output, rubric))
    minimum = int(spec.get("min_score", 4))
    return _ok("llm_judge", score >= minimum, f"{rubric}={score} (min {minimum})")


@register("custom")
def _custom(resp: AgentResponse, spec: dict) -> AssertionResult:
    target = str(spec["path"])
    module_name, _, func_name = target.partition(":")
    fn = getattr(importlib.import_module(module_name), func_name)
    outcome = fn(resp)
    if isinstance(outcome, tuple):
        passed, detail = outcome
    else:
        passed, detail = bool(outcome), ""
    return _ok("custom", bool(passed), str(detail))


def evaluate(resp: AgentResponse, specs: list[dict[str, Any]]) -> list[AssertionResult]:
    out: list[AssertionResult] = []
    for spec in specs:
        kind = str(spec.get("type", ""))
        fn = REGISTRY.get(kind)
        if fn is None:
            out.append(_ok(kind or "<missing>", False, f"unknown assertion type {kind!r}"))
            continue
        try:
            out.append(fn(resp, spec))
        except Exception as exc:  # noqa: BLE001
            out.append(_ok(kind, False, f"{type(exc).__name__}: {exc}"))
    return out

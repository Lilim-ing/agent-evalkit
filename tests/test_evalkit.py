import json

import pytest

from evalkit.assertions import REGISTRY, evaluate
from evalkit.schema import AgentResponse, TraceEvent
from evalkit.stats import (
    bootstrap_ci,
    calibration_verdict,
    cohen_kappa,
    regression_diff,
    summarize,
)


def resp(output="", tools=None, cost=0.0, latency=0.0) -> AgentResponse:
    return AgentResponse(
        output=output,
        trace=[TraceEvent(type="tool_call", name=t) for t in (tools or [])],
        cost_usd=cost,
        latency_ms=latency,
    )


def one(spec, response):
    results = evaluate(response, [spec])
    assert len(results) == 1
    return results[0]


def test_contains_and_not_contains():
    assert one({"type": "contains", "value": "复购"}, resp("复购率下滑")).passed
    assert not one({"type": "contains", "value": "流失"}, resp("复购率下滑")).passed
    assert one({"type": "not_contains", "value": "保证"}, resp("复购率下滑")).passed


def test_regex():
    assert one({"type": "regex", "pattern": r"客单价\s*\d+"}, resp("客单价 287 元")).passed


def test_json_has_and_numeric_close():
    payload = json.dumps({"kpi": {"aov": 287.0}})
    assert one({"type": "json_has", "keys": ["kpi"]}, resp(payload)).passed
    assert one({"type": "numeric_close", "path": "$.kpi.aov", "value": 287, "tol": 1}, resp(payload)).passed
    assert not one({"type": "numeric_close", "path": "$.kpi.aov", "value": 300, "tol": 1}, resp(payload)).passed


def test_numeric_close_rejects_non_numeric():
    payload = json.dumps({"kpi": {"aov": None}})
    result = one({"type": "numeric_close", "path": "$.kpi.aov", "value": 1}, resp(payload))
    assert not result.passed
    assert "not numeric" in result.detail


def test_tool_assertions():
    r = resp("x", tools=["query_cohort", "decompose_metric"])
    assert one({"type": "tool_called", "tool": "query_cohort"}, r).passed
    assert not one({"type": "tool_called", "tool": "drop_table"}, r).passed
    assert one({"type": "tool_not_called", "tool": "drop_table"}, r).passed
    assert one({"type": "tool_order", "tools": ["query_cohort", "decompose_metric"]}, r).passed
    assert not one({"type": "tool_order", "tools": ["decompose_metric", "query_cohort"]}, r).passed


def test_budget_assertions():
    r = resp("x", cost=0.02, latency=900)
    assert one({"type": "max_cost", "value": 0.03}, r).passed
    assert not one({"type": "max_cost", "value": 0.01}, r).passed
    assert one({"type": "max_latency_ms", "value": 1000}, r).passed


def test_evidence_assertions():
    payload = json.dumps(
        {
            "evidence_ids": ["e1"],
            "claims": [
                {"id": "c1", "evidence_ids": ["e1"]},
                {"id": "c2", "evidence_ids": []},
            ],
        }
    )
    r = resp(payload)
    assert not one({"type": "evidence_coverage", "min": 0.9}, r).passed
    assert not one({"type": "no_orphan_claims"}, r).passed


def test_unknown_assertion_fails_loudly():
    result = one({"type": "does_not_exist"}, resp("x"))
    assert not result.passed
    assert "unknown assertion" in result.detail


def test_exception_in_assertion_is_caught():
    result = one({"type": "regex", "pattern": "["}, resp("x"))
    assert not result.passed
    assert "error" in result.detail.lower() or "unterminated" in result.detail.lower()


def test_registry_contains_builtins():
    for name in ("contains", "tool_called", "numeric_close", "evidence_coverage", "llm_judge"):
        assert name in REGISTRY


def test_bootstrap_ci_is_deterministic():
    values = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0]
    assert bootstrap_ci(values) == bootstrap_ci(values)
    lo, hi = bootstrap_ci(values)
    assert 0.0 <= lo <= hi <= 1.0


def test_cohen_kappa_perfect_and_chance():
    assert cohen_kappa([True, False, True], [True, False, True]) == 1.0
    # 50/50 labels with no agreement beyond chance
    assert cohen_kappa([True, True, False, False], [True, False, True, False]) == 0.0
    with pytest.raises(ValueError):
        cohen_kappa([True], [True, False])


def test_calibration_verdict_thresholds():
    assert calibration_verdict(0.85)[0] == "good"
    assert calibration_verdict(0.65)[0] == "fair"
    assert calibration_verdict(0.4)[0] == "poor"


def test_summary_marks_flaky():
    from evalkit.schema import CaseResult

    results = [
        CaseResult(case_id="a", run=1, passed=True),
        CaseResult(case_id="a", run=2, passed=False),
        CaseResult(case_id="b", run=1, passed=True),
        CaseResult(case_id="b", run=2, passed=True),
    ]
    summaries = {s.case_id: s for s in summarize(results)}
    assert summaries["a"].flaky is True
    assert summaries["a"].pass_rate == 0.5
    assert summaries["b"].flaky is False


def test_regression_diff_classifies():
    diff = regression_diff({"a": 0.5, "b": 1.0, "c": 0.0}, {"a": 1.0, "b": 0.4, "c": 0.0})
    assert [x["case"] for x in diff["fixed"]] == ["a"]
    assert [x["case"] for x in diff["regressed"]] == ["b"]
    assert [x["case"] for x in diff["stable"]] == ["c"]


def test_regression_diff_does_not_call_missing_cases_regressions():
    """Comparing two different suites must not invent regressions."""
    diff = regression_diff({"a": 1.0, "b": 1.0}, {"a": 1.0, "c": 1.0})
    assert [x["case"] for x in diff["removed"]] == ["b"]
    assert [x["case"] for x in diff["added"]] == ["c"]
    assert diff["regressed"] == []


def test_cost_source_is_carried_into_the_report():
    """A cost figure must state where it came from, so a simulated number is
    never read as real spend."""
    from evalkit.runner import Runner
    from evalkit.schema import Case

    def fake_agent(_):
        return AgentResponse(output="ok", cost_usd=0.012, cost_source="simulated")

    report = Runner(fake_agent).run_suite([Case(id="c1", input="q", assertions=[])])
    assert report.total_cost_usd == 0.012
    assert report.cost_basis == "simulated"
    assert report.results[0].cost_source == "simulated"


def test_default_cost_basis_is_none():
    from evalkit.runner import Runner
    from evalkit.schema import Case

    def free_agent(_):
        return "ok"

    report = Runner(free_agent).run_suite([Case(id="c1", input="q", assertions=[])])
    assert report.cost_basis == "none"

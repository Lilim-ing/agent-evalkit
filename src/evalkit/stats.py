"""Statistics: confidence intervals, flakiness, judge calibration."""

from __future__ import annotations

import random
from collections import defaultdict

from .schema import CaseResult, CaseSummary


def bootstrap_ci(
    values: list[float], n_resamples: int = 2000, alpha: float = 0.05, seed: int = 42
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean. Seeded, so reports are reproducible."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int((alpha / 2) * n_resamples)]
    hi = means[int((1 - alpha / 2) * n_resamples) - 1]
    return (round(lo, 4), round(hi, 4))


def summarize(results: list[CaseResult], flaky_threshold: float = 0.2) -> list[CaseSummary]:
    grouped: dict[str, list[CaseResult]] = defaultdict(list)
    for r in results:
        grouped[r.case_id].append(r)

    summaries = []
    for case_id, rows in grouped.items():
        runs = len(rows)
        passes = sum(1 for r in rows if r.passed)
        rate = passes / runs
        failures = sorted({a.type for r in rows for a in r.assertions if not a.passed})
        summaries.append(
            CaseSummary(
                case_id=case_id,
                runs=runs,
                passes=passes,
                pass_rate=round(rate, 4),
                # A case that sometimes passes and sometimes fails is not "mostly
                # working"; it is unstable, and must be reported as such.
                flaky=0.0 < rate < 1.0,
                mean_cost_usd=round(sum(r.cost_usd for r in rows) / runs, 6),
                mean_latency_ms=round(sum(r.latency_ms for r in rows) / runs, 1),
                failures=failures,
            )
        )
    summaries.sort(key=lambda s: s.case_id)
    return summaries


def cohen_kappa(labels_a: list[bool], labels_b: list[bool]) -> float:
    """Agreement between two raters, corrected for chance."""
    if len(labels_a) != len(labels_b) or not labels_a:
        raise ValueError("label lists must be non-empty and the same length")
    n = len(labels_a)
    observed = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n
    pa = sum(1 for a in labels_a if a) / n
    pb = sum(1 for b in labels_b if b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected == 1.0:
        return 1.0
    return round((observed - expected) / (1 - expected), 4)


def calibration_verdict(kappa: float) -> tuple[str, str]:
    """Return (level, message). Thresholds are deliberately conservative."""
    if kappa >= 0.8:
        return "good", "judge 与人工高度一致，可用于门禁"
    if kappa >= 0.6:
        return "fair", "judge 一致性可用，但建议只对高分差做门禁"
    return "poor", "judge 一致性不足，不应作为 CI 门禁；先改 rubric 或补标注"


def regression_diff(baseline: dict[str, float], current: dict[str, float], tol: float = 0.05) -> dict:
    """Classify each case: fixed / regressed / stable, plus added / removed.

    A case that only exists in one of the two reports is NOT a regression. It is
    a different case set, and conflating the two produces phantom regressions
    when someone compares two different suites by mistake.
    """
    fixed, regressed, stable, added, removed = [], [], [], [], []
    for case_id in sorted(set(baseline) | set(current)):
        if case_id not in current:
            removed.append({"case": case_id, "before": baseline[case_id], "after": None})
            continue
        if case_id not in baseline:
            added.append({"case": case_id, "before": None, "after": current[case_id]})
            continue
        before = baseline[case_id]
        after = current[case_id]
        if after - before > tol:
            fixed.append({"case": case_id, "before": before, "after": after})
        elif before - after > tol:
            regressed.append({"case": case_id, "before": before, "after": after})
        else:
            stable.append({"case": case_id, "before": before, "after": after})
    return {
        "fixed": fixed,
        "regressed": regressed,
        "stable": stable,
        "added": added,
        "removed": removed,
    }

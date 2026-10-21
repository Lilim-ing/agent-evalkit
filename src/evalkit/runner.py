"""Suite runner."""

from __future__ import annotations

from typing import Any, Callable

import yaml

from . import assertions as assertion_mod
from .adapters import FunctionAdapter, normalize
from .schema import Case, CaseResult, Report, now_iso
from .stats import bootstrap_ci, summarize


def load_cases(path: str) -> tuple[str, list[Case]]:
    data = yaml.safe_load(open(path, encoding="utf-8"))  # noqa: SIM115
    suite = data.get("suite", "default")
    cases = [Case(**raw) for raw in data.get("cases", [])]
    if not cases:
        raise ValueError(f"no cases in {path}")
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    return suite, cases


class Runner:
    def __init__(
        self,
        adapter: FunctionAdapter | Callable[[str], Any],
        judge: Callable[[str, str], int] | None = None,
    ) -> None:
        self.adapter = adapter if isinstance(adapter, FunctionAdapter) else FunctionAdapter(adapter)
        assertion_mod.set_judge(judge)

    def run_case(self, case: Case) -> list[CaseResult]:
        results: list[CaseResult] = []
        for i in range(max(1, case.repeat)):
            try:
                response = normalize(self.adapter(case.input))
                checks = assertion_mod.evaluate(response, case.assertions)
                results.append(
                    CaseResult(
                        case_id=case.id,
                        run=i + 1,
                        passed=all(c.passed for c in checks),
                        assertions=checks,
                        cost_usd=response.cost_usd,
                        cost_source=response.cost_source,
                        latency_ms=response.latency_ms,
                        output_digest=CaseResult.digest_output(response.output),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                results.append(
                    CaseResult(
                        case_id=case.id,
                        run=i + 1,
                        passed=False,
                        assertions=[
                            assertion_mod._ok("adapter", False, f"{type(exc).__name__}: {exc}")
                        ],
                    )
                )
        return results

    def run_suite(self, cases: list[Case], suite: str = "default") -> Report:
        started = now_iso()
        results: list[CaseResult] = []
        for case in cases:
            results.extend(self.run_case(case))
        finished = now_iso()

        summaries = summarize(results)
        pass_flags = [1.0 if r.passed else 0.0 for r in results]
        rate = sum(pass_flags) / len(pass_flags) if pass_flags else 0.0

        sources = {r.cost_source for r in results}
        if "actual" in sources:
            # Any real spend makes the total a real total; if simulated figures
            # are mixed in, say so rather than round the whole thing to "actual".
            cost_basis = "mixed" if sources & {"simulated", "none"} else "actual"
        elif "simulated" in sources:
            # A run where some cases errored out (no cost) is still a simulated
            # run, not a partially-real one.
            cost_basis = "simulated"
        else:
            cost_basis = "none"

        return Report(
            suite=suite,
            started_at=started,
            finished_at=finished,
            adapter=getattr(self.adapter, "name", "callable"),
            results=results,
            summaries=summaries,
            pass_rate=round(rate, 4),
            pass_ci=bootstrap_ci(pass_flags),
            total_cost_usd=round(sum(r.cost_usd for r in results), 6),
            cost_basis=cost_basis,
            mean_latency_ms=round(sum(r.latency_ms for r in results) / max(len(results), 1), 1),
            flaky_cases=sum(1 for s in summaries if s.flaky),
        )

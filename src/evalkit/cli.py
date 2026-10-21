"""CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .adapters import load_adapter
from .report import cost_label, diff_markdown, write_reports
from .runner import Runner, load_cases
from .stats import calibration_verdict, cohen_kappa, regression_diff

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

app = typer.Typer(add_completion=False, help="evalkit · Agent 评测与回归工具包")
console = Console()


@app.command()
def run(
    cases: str = typer.Argument(..., help="cases.yaml 路径"),
    adapter: str = typer.Option("examples.toy_agent:agent", help="module:function"),
    out: str = typer.Option("reports/report", "-o", "--out", help="输出前缀（生成 .md/.html/.json）"),
    repeat: int = typer.Option(0, help="覆盖每个用例的重复次数；0 表示用 YAML 里的值"),
) -> None:
    """跑一轮评测。"""
    suite, items = load_cases(cases)
    if repeat > 0:
        for item in items:
            item.repeat = repeat
    runner = Runner(load_adapter(adapter))
    report = runner.run_suite(items, suite)
    paths = write_reports(report, out)

    table = Table(show_header=True, header_style="bold")
    table.add_column("case")
    table.add_column("通过")
    table.add_column("通过率")
    table.add_column("状态")
    for s in report.summaries:
        state = "不稳定" if s.flaky else ("通过" if s.pass_rate == 1.0 else "失败")
        table.add_row(s.case_id, f"{s.passes}/{s.runs}", f"{s.pass_rate:.0%}", state)
    console.print(table)
    console.print(
        f"\n通过率 [bold]{report.pass_rate:.1%}[/bold] "
        f"(95% CI {report.pass_ci[0]:.1%}–{report.pass_ci[1]:.1%}) · "
        f"不稳定 {report.flaky_cases} · 成本 ${report.total_cost_usd:.4f}"
        f"（{cost_label(report.cost_basis)}）"
    )
    console.print(f"报告：{paths['html']}")
    if report.pass_rate < 1.0 or report.flaky_cases:
        raise typer.Exit(code=1)


@app.command()
def compare(
    baseline: str = typer.Argument(..., help="基线 report.json"),
    current: str = typer.Argument(..., help="当前 report.json"),
) -> None:
    """对比两次评测，区分修复 / 退化 / 稳定。"""
    base = json.loads(Path(baseline).read_text(encoding="utf-8"))
    curr = json.loads(Path(current).read_text(encoding="utf-8"))
    if base.get("suite") != curr.get("suite"):
        console.print(
            f"[yellow]注意：两次报告来自不同套件（{base.get('suite')} vs {curr.get('suite')}），"
            "用例集合不同，只有同名用例才可比较[/yellow]\n"
        )
    b = {s["case_id"]: s["pass_rate"] for s in base["summaries"]}
    c = {s["case_id"]: s["pass_rate"] for s in curr["summaries"]}
    diff = regression_diff(b, c)
    console.print(diff_markdown(diff))
    if diff["regressed"]:
        raise typer.Exit(code=1)


@app.command()
def calibrate(
    labels: str = typer.Argument(..., help="jsonl，每行 {human: 0/1, judge: 0/1}"),
    min_kappa: float = typer.Option(0.6, help="可用于门禁的最低 κ"),
) -> None:
    """计算 judge 与人工标注的一致性。"""
    rows = [json.loads(line) for line in Path(labels).read_text(encoding="utf-8").splitlines() if line.strip()]
    human = [bool(r["human"]) for r in rows]
    judge = [bool(r["judge"]) for r in rows]
    kappa = cohen_kappa(human, judge)
    level, message = calibration_verdict(kappa)
    agreement = sum(1 for a, b in zip(human, judge) if a == b) / len(rows)
    console.print(f"样本 {len(rows)} · 一致率 {agreement:.1%} · Cohen's κ = [bold]{kappa}[/bold] ({level})")
    console.print(message)
    if kappa < min_kappa:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

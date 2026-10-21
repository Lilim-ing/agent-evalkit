"""Markdown and single-file HTML reports."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .schema import Report

COST_LABEL = {
    "actual": "实际计费",
    "simulated": "模拟值，未调用任何模型",
    "none": "未产生成本",
    "mixed": "实际与模拟混合",
}


def cost_label(basis: str) -> str:
    return COST_LABEL.get(basis, basis)


def to_markdown(report: Report) -> str:
    lines = [
        f"# 评测报告 · {report.suite}",
        "",
        f"> adapter `{report.adapter}` · {report.started_at} → {report.finished_at}",
        f"> 通过率 **{report.pass_rate:.1%}**（95% CI {report.pass_ci[0]:.1%} – {report.pass_ci[1]:.1%}）",
        f"> 成本 ${report.total_cost_usd:.4f}（{cost_label(report.cost_basis)}）"
        f" · 平均延迟 {report.mean_latency_ms:.0f}ms · 不稳定用例 {report.flaky_cases}",
        "",
        "## 用例",
        "",
        "| case | runs | pass | 通过率 | flaky | 主要失败断言 |",
        "|---|---|---|---|---|---|",
    ]
    for s in report.summaries:
        mark = "⚠️" if s.flaky else ("✅" if s.pass_rate == 1.0 else "❌")
        lines.append(
            f"| `{s.case_id}` | {s.runs} | {s.passes} | {s.pass_rate:.0%} {mark} | "
            f"{'是' if s.flaky else '否'} | {', '.join(s.failures) or '-'} |"
        )

    failures = [r for r in report.results if not r.passed]
    lines += ["", "## 失败明细", ""]
    if not failures:
        lines.append("无。")
    else:
        for r in failures:
            bad = [f"{a.type}: {a.detail}" for a in r.assertions if not a.passed]
            lines.append(f"- `{r.case_id}` run {r.run} — {'; '.join(bad)}")

    lines += [
        "",
        "## 读法",
        "",
        "- **flaky** 表示同一用例多次运行时而通过时而失败。它不是「基本可用」，是不稳定，必须单独处理。",
        "- 置信区间来自 bootstrap（2000 次重采样，固定种子），用于判断通过率差异是否显著。",
        "- `llm_judge` 断言的可信度取决于 judge 与人工标注的一致性（κ），见 `evalkit calibrate`。",
        "",
    ]
    return "\n".join(lines)


def to_html(report: Report) -> str:
    rows = []
    for s in report.summaries:
        status = "flaky" if s.flaky else ("pass" if s.pass_rate == 1.0 else "fail")
        label = {"flaky": "不稳定", "pass": "通过", "fail": "失败"}[status]
        rows.append(
            f"<tr class='{status}'><td><code>{html.escape(s.case_id)}</code></td>"
            f"<td>{s.runs}</td><td>{s.passes}</td><td>{s.pass_rate:.0%}</td>"
            f"<td><span class='badge {status}'>{label}</span></td>"
            f"<td>{html.escape(', '.join(s.failures) or '-')}</td></tr>"
        )

    details = []
    for r in report.results:
        if r.passed:
            continue
        bad = [a for a in r.assertions if not a.passed]
        details.append(
            f"<div class='fail'><div class='fail-h'>{html.escape(r.case_id)} · run {r.run}</div>"
            + "".join(
                f"<div class='fail-i'><code>{html.escape(a.type)}</code> {html.escape(a.detail)}</div>"
                for a in bad
            )
            + "</div>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>evalkit · {html.escape(report.suite)}</title>
<style>
  :root {{ --bg:#f7f8fa; --card:#fff; --ink:#111827; --muted:#6b7280; --line:#e5e7eb;
           --ok:#047857; --bad:#b91c1c; --warn:#b45309; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }}
  .wrap {{ max-width:1000px; margin:0 auto; padding:34px 20px 70px; }}
  h1 {{ font-size:22px; margin:0 0 6px; }}
  .sub {{ color:var(--muted); font-size:12.5px; font-family:ui-monospace,Menlo,Consolas,monospace; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:22px 0; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:13px 15px; }}
  .card .k {{ font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
  .card .v {{ font-size:20px; font-weight:650; margin-top:3px; }}
  .card .sub {{ font-size:10.5px; color:var(--muted); margin-top:2px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line);
    border-radius:10px; overflow:hidden; font-size:13px; }}
  th, td {{ text-align:left; padding:9px 12px; border-bottom:1px solid #f1f5f9; }}
  th {{ font-size:11.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
  tr.flaky {{ background:#fffbeb; }}
  .badge {{ padding:2px 9px; border-radius:999px; font-size:11.5px; font-weight:600; }}
  .badge.pass {{ background:#dcfce7; color:var(--ok); }}
  .badge.fail {{ background:#fee2e2; color:var(--bad); }}
  .badge.flaky {{ background:#fef3c7; color:var(--warn); }}
  .fail {{ background:var(--card); border:1px solid var(--line); border-left:3px solid var(--bad);
    border-radius:8px; padding:11px 14px; margin-bottom:9px; }}
  .fail-h {{ font-weight:650; font-size:13px; margin-bottom:5px; }}
  .fail-i {{ font-size:12.5px; color:#374151; line-height:1.8; }}
  h2 {{ font-size:12.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin:26px 0 10px; }}
  code {{ font-family:ui-monospace,Menlo,Consolas,monospace; font-size:12px; }}
</style></head><body><div class="wrap">
  <h1>评测报告 · {html.escape(report.suite)}</h1>
  <div class="sub">{html.escape(report.adapter)} · {html.escape(report.started_at)}</div>
  <div class="cards">
    <div class="card"><div class="k">通过率</div><div class="v">{report.pass_rate:.1%}</div></div>
    <div class="card"><div class="k">95% CI</div><div class="v">{report.pass_ci[0]:.1%}–{report.pass_ci[1]:.1%}</div></div>
    <div class="card"><div class="k">用例数</div><div class="v">{len(report.summaries)}</div></div>
    <div class="card"><div class="k">不稳定</div><div class="v">{report.flaky_cases}</div></div>
    <div class="card"><div class="k">总成本</div><div class="v">${report.total_cost_usd:.4f}</div>
      <div class="sub">{html.escape(cost_label(report.cost_basis))}</div></div>
    <div class="card"><div class="k">平均延迟</div><div class="v">{report.mean_latency_ms:.0f}ms</div></div>
  </div>
  <h2>用例</h2>
  <table><thead><tr><th>case</th><th>runs</th><th>pass</th><th>通过率</th><th>状态</th><th>失败断言</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
  <h2>失败明细</h2>
  {''.join(details) or '<div class="sub">无失败用例</div>'}
</div></body></html>"""


def write_reports(report: Report, out_prefix: str | Path) -> dict[str, Path]:
    prefix = Path(out_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    md = prefix.with_suffix(".md")
    html_path = prefix.with_suffix(".html")
    js = prefix.with_suffix(".json")
    md.write_text(to_markdown(report), encoding="utf-8")
    html_path.write_text(to_html(report), encoding="utf-8")
    js.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": md, "html": html_path, "json": js}


def diff_markdown(diff: dict) -> str:
    lines = ["# 回归对比", ""]
    rows = [
        ("fixed", "修复"),
        ("regressed", "退化"),
        ("stable", "稳定"),
        ("added", "新增用例"),
        ("removed", "移除用例"),
    ]
    for key, title in rows:
        items = diff.get(key, [])
        lines.append(f"## {title}（{len(items)}）")
        lines.append("")
        if not items:
            lines.append("无。")
        else:
            for it in items:
                before = "—" if it["before"] is None else f"{it['before']:.0%}"
                after = "—" if it["after"] is None else f"{it['after']:.0%}"
                lines.append(f"- `{it['case']}`：{before} → {after}")
        lines.append("")
    return "\n".join(lines)

# 评测报告 · toy-agent-negative-controls

> adapter `examples.toy_agent:agent` · 2026-10-21T11:03:29+08:00 → 2026-10-21T11:03:29+08:00
> 通过率 **33.3%**（95% CI 0.0% – 66.7%）
> 成本 $0.0160（模拟值，未调用任何模型） · 平均延迟 560ms · 不稳定用例 1

## 用例

| case | runs | pass | 通过率 | flaky | 主要失败断言 |
|---|---|---|---|---|---|
| `adapter_error` | 1 | 0 | 0% ❌ | 否 | adapter |
| `flaky_tool` | 4 | 2 | 50% ⚠️ | 是 | tool_called |
| `missing_evidence` | 1 | 0 | 0% ❌ | 否 | evidence_coverage, no_orphan_claims |

## 失败明细

- `missing_evidence` run 1 — evidence_coverage: 1/2 = 0.50; no_orphan_claims: orphans: ['c2']
- `flaky_tool` run 2 — tool_called: tools used: ['query_other']
- `flaky_tool` run 4 — tool_called: tools used: ['query_other']
- `adapter_error` run 1 — adapter: RuntimeError: simulated adapter failure

## 读法

- **flaky** 表示同一用例多次运行时而通过时而失败。它不是「基本可用」，是不稳定，必须单独处理。
- 置信区间来自 bootstrap（2000 次重采样，固定种子），用于判断通过率差异是否显著。
- `llm_judge` 断言的可信度取决于 judge 与人工标注的一致性（κ），见 `evalkit calibrate`。

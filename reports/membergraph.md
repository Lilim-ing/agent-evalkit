# 评测报告 · membergraph-dogfood

> adapter `examples.membergraph_eval:agent` · 2026-10-21T09:57:58+08:00 → 2026-10-21T09:58:00+08:00
> 通过率 **100.0%**（95% CI 100.0% – 100.0%）
> 成本 $0.0079 · 平均延迟 217ms · 不稳定用例 0

## 用例

| case | runs | pass | 通过率 | flaky | 主要失败断言 |
|---|---|---|---|---|---|
| `aov_upt_plan` | 2 | 2 | 100% ✅ | 否 | - |
| `churn_plan` | 2 | 2 | 100% ✅ | 否 | - |
| `repurchase_plan` | 2 | 2 | 100% ✅ | 否 | - |

## 失败明细

无。

## 读法

- **flaky** 表示同一用例多次运行时而通过时而失败。它不是「基本可用」，是不稳定，必须单独处理。
- 置信区间来自 bootstrap（2000 次重采样，固定种子），用于判断通过率差异是否显著。
- `llm_judge` 断言的可信度取决于 judge 与人工标注的一致性（κ），见 `evalkit calibrate`。

# 评测报告 · toy-agent-quality

> adapter `examples.toy_agent:agent` · 2026-10-21T11:03:30+08:00 → 2026-10-21T11:03:30+08:00
> 通过率 **100.0%**（95% CI 100.0% – 100.0%）
> 成本 $0.0510（模拟值，未调用任何模型） · 平均延迟 828ms · 不稳定用例 0

## 用例

| case | runs | pass | 通过率 | flaky | 主要失败断言 |
|---|---|---|---|---|---|
| `aov_and_upt` | 2 | 2 | 100% ✅ | 否 | - |
| `churn_rise` | 2 | 2 | 100% ✅ | 否 | - |
| `cost_ceiling` | 1 | 1 | 100% ✅ | 否 | - |
| `forbidden_claim` | 1 | 1 | 100% ✅ | 否 | - |
| `json_shape` | 1 | 1 | 100% ✅ | 否 | - |
| `no_forbidden_tool` | 1 | 1 | 100% ✅ | 否 | - |
| `regex_format` | 1 | 1 | 100% ✅ | 否 | - |
| `repurchase_diagnosis` | 3 | 3 | 100% ✅ | 否 | - |

## 失败明细

无。

## 读法

- **flaky** 表示同一用例多次运行时而通过时而失败。它不是「基本可用」，是不稳定，必须单独处理。
- 置信区间来自 bootstrap（2000 次重采样，固定种子），用于判断通过率差异是否显著。
- `llm_judge` 断言的可信度取决于 judge 与人工标注的一致性（κ），见 `evalkit calibrate`。

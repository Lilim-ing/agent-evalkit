# agent-evalkit

Agent 评测与回归工具包。给 Agent 的最终输出和调用过程写断言，报告能对比两次运行，也可以放进 CI 卡回归。

```bash
pip install -e ".[dev]"
evalkit run evals/cases.yaml -o reports/baseline
```

零外部依赖，不需要 API key，任何返回字符串 / dict / `AgentResponse` 的函数都能接。

---

## 背景

大多数 Agent 评测只比对最终输出的一段文本。但 Agent 的错误往往发生在过程里：

- 工具调错了 → 输出可能碰巧还对
- 工具顺序反了 → 结果对了但逻辑不成立
- 预算超了 3 倍 → 文本看起来完美

所以断言的对象是整个 `AgentResponse`：

```python
AgentResponse(
    output="...",                    # 最终回答
    trace=[TraceEvent(type="tool_call", name="query_cohort"), ...],
    cost_usd=0.004,
    latency_ms=820,
)
```

---

## 断言 DSL

```yaml
case: repurchase_diagnosis
input: "9月复购率为什么下滑"
repeat: 3
assertions:
  - {type: tool_called, tool: query_cohort}
  - {type: tool_order, tools: [query_cohort, decompose_metric]}
  - {type: evidence_coverage, min: 0.9}
  - {type: no_orphan_claims}
  - {type: numeric_close, path: "$.kpi.repurchase_rate", value: 0.131, tol: 0.002}
  - {type: max_cost, value: 0.01}
  - {type: llm_judge, rubric: actionability, min_score: 4}
  - {type: custom, path: "examples.toy_agent:has_two_claims"}
```

| 断言 | 检查什么 |
|---|---|
| `contains` / `not_contains` / `regex` | 文本 |
| `json_has` | 输出 JSON 的必填字段 |
| `numeric_close` | 按 JSON path 取数，带容差 |
| `tool_called` / `tool_not_called` | 是否调用了某个工具 |
| `tool_order` | 工具调用顺序（子序列匹配） |
| `max_cost` / `max_latency_ms` | 预算与延迟 |
| `evidence_coverage` | 有证据的结论占比 |
| `no_orphan_claims` | 是否存在引用不存在证据的结论 |
| `llm_judge` | 评分（需校准，见下） |
| `custom` | 任意 `module:function`，返回 `(bool, detail)` |

新增断言只需要 `@register("name")`，十行以内。

---

## 稳定性

同一用例跑 4 次，2 次通过 2 次失败 → `flaky=True`，报告里单独标黄。

只跑一次就报通过，这个结论不可靠：用例可能本身就不稳定，也可能只是这次碰巧。

通过率不写成单点估计，每个数字后面带 bootstrap 区间：

```
通过率 100.0% (95% CI 100.0%–100.0%)
```

bootstrap 2000 次重采样，固定种子。样本少时区间会明显变宽，说明这个数字还不稳。

---

## judge 校准

```bash
evalkit calibrate evals/judge_labels.jsonl
# 样本 30 · 一致率 86.7% · Cohen's κ = 0.7333 (fair)
# judge 一致性可用，但建议只对高分差做门禁
```

κ < 0.6 时报告会写明"不应作为 CI 门禁"。LLM-as-judge 用得很多，但校准常常被跳过；没校准的一致性分数只能当参考，不能用来卡门禁。

---

## 评测结果（2026-10-21）

主套件（8 个用例 / 12 次运行）：

| 指标 | 值 |
|---|---|
| 通过率 | 100%（95% CI 100%–100%） |
| 不稳定用例 | 0 |
| 总成本 | $0.0510（模拟值，未调用任何模型） |

### 关于成本数字

仓库里出现的 `$0.0510` / `$0.0160` 都是 toy agent 里硬编码的演示值：

- `examples/toy_agent.py` 每个返回值写死了 `cost_usd: 0.003 ~ 0.005`
- `$0.0160 = 0.004×1`（missing_evidence）`+ 0.003×4`（flaky_tool）`+ 0×1`（adapter_error 未返回，不计成本）
- 整个仓库没有任何网络请求、没有模型、没有 API key，实际花费 0 元

保留这个字段是为了让 `max_cost` 断言和"成本预算"评测维度能离线演示。真实接入时，adapter 从服务端 usage 拿到的金额要标 `cost_source="actual"`，报告标签会自动变成"实际计费"；两者混用时显示"实际与模拟混合"。

```python
AgentResponse(output="...", cost_usd=0.012, cost_source="actual")
```

负向对照（3 个用例，用来验证框架能识别问题）：

| 用例 | 结果 | 框架判定 |
|---|---|---|
| `missing_evidence` | 0/1 | 失败（证据覆盖率 0.50） |
| `flaky_tool` | 2/4 | 不稳定 |
| `adapter_error` | 0/1 | 失败（适配器异常被捕获） |

负向对照不计入主套件通过率。

### 跨仓库联调

用本工具评测隔壁的 `membergraph`（需两个仓库并排 checkout，并先安装它的依赖）：

```bash
pip install -e ../membergraph          # 跨仓库示例需要 membergraph 的依赖
evalkit run evals/membergraph_cases.yaml \
  --adapter examples.membergraph_eval:agent \
  -o reports/membergraph
```

实测：3 个用例 / 6 次运行，100% 通过，成本 $0.0079。断言覆盖证据覆盖率、孤儿结论、工具调用、成本上限、动作完整性、非降级状态。

若未安装依赖，报告里会给出可读的失败原因（而不是一段 traceback），提示 `pip install -e ../membergraph`。

```bash
python -m pytest    # 18 passed
```

---

## 快速开始

```bash
pip install -e ".[dev]"

# 1. 跑自带示例
evalkit run evals/cases.yaml -o reports/baseline

# 2. 验证框架能发现问题
evalkit run evals/negative_controls.yaml -o reports/negative

# 3. 对比两次运行
evalkit compare reports/baseline.json reports/negative.json

# 4. 校准 judge
evalkit calibrate evals/judge_labels.jsonl
```

接入自己的 Agent：

```python
# my_agent.py
def agent(question: str) -> dict:
    return {
        "output": "...",
        "trace": [{"type": "tool_call", "name": "search"}],
        "cost_usd": 0.003,
        "latency_ms": 420,
    }
```

```bash
evalkit run my_cases.yaml --adapter my_agent:agent
```

HTTP 与 CLI 适配器见 `src/evalkit/adapters.py`。

---

## 设计取舍

### 没有绑定可观测平台

LangSmith / LangFuse 解决"看"的问题，这个项目解决"判"的问题，而且要能进 CI 卡住回归。两者可以并存：trace 格式是普通 JSON，导出到任何平台都行。

### 自带的 judge 是启发式的

为了校准流程能离线跑。它明确标注为 heuristic，README 和代码里都写了不要用它做门禁。接真实模型只需传一个函数。

### repeat 放在 case 级

核心用例多跑几次看稳定性，便宜的用例跑一次就够。全局 repeat 会让成本失控。

---

## 目录

```
agent-evalkit/
├── src/evalkit/
│   ├── schema.py        # AgentResponse / Case / Report
│   ├── assertions.py    # 11 种断言 + 注册表
│   ├── stats.py         # bootstrap / flaky / kappa / diff
│   ├── adapters.py      # function / http / cli
│   ├── runner.py        # 套件执行
│   ├── report.py        # markdown + 单文件 HTML
│   └── cli.py
├── examples/toy_agent.py
├── evals/               # 主套件 + 负向对照 + 标注
├── tests/               # 18 个测试
└── docs/                # DSL 与校准说明
```

---

## 边界

- judge 默认是启发式，不是模型；真实 judge 的一致性需要你自己标注并校准
- 只做离线批量评测，不做在线监控与采样
- trace 格式是自定义的，与 OpenTelemetry GenAI 语义约定尚未对齐
- 无并发执行；大套件会串行跑

## License

MIT

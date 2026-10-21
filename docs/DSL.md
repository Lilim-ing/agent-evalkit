# 断言 DSL

## 结构

```yaml
suite: my-suite
cases:
  - id: unique_id          # 必填，套件内唯一
    input: "..."           # 传给 adapter 的字符串
    repeat: 1              # 运行次数，>1 用于稳定性检测
    tags: [core]           # 可选，仅用于组织
    assertions:
      - {type: contains, value: "复购"}
```

## 断言清单

### 文本类

| type | 参数 | 说明 |
|---|---|---|
| `contains` | `value` | 输出包含子串 |
| `not_contains` | `value` | 输出不包含子串（用于禁用词） |
| `regex` | `pattern` | 正则搜索 |

### 结构类

| type | 参数 | 说明 |
|---|---|---|
| `json_has` | `keys: []` | 输出是 JSON 对象且含这些顶层字段 |
| `numeric_close` | `path`, `value`, `tol` | 按 JSON path 取数并比较；非数值直接失败 |
| `evidence_coverage` | `min` | `claims` 中带 `evidence_ids` 的比例 |
| `no_orphan_claims` | — | 不存在空引用或引用未知 evidence 的 claim |

`path` 语法：`$.kpi.aov`、`$.claims.0.id`（数组用下标）。

### Trace 类

| type | 参数 | 说明 |
|---|---|---|
| `tool_called` | `tool` | trace 中出现该工具 |
| `tool_not_called` | `tool` | 未出现 |
| `tool_order` | `tools: []` | 期望顺序是实际顺序的子序列 |

### 预算类

| type | 参数 | 说明 |
|---|---|---|
| `max_cost` | `value` | 成本上限（美元） |
| `max_latency_ms` | `value` | 延迟上限（毫秒） |

### 质量类

| type | 参数 | 说明 |
|---|---|---|
| `llm_judge` | `rubric`, `min_score` | 评分；judge 需校准 |
| `custom` | `path: "module:function"` | 自定义断言，函数接收 `AgentResponse`，返回 `bool` 或 `(bool, detail)` |

## 自定义断言

```python
from evalkit.assertions import register

@register("has_action")
def _has_action(resp, spec):
    passed = any(k in resp.output for k in ("人群", "渠道", "预算"))
    return __import__("evalkit.schema", fromlist=["AssertionResult"]).AssertionResult(
        type="has_action", passed=passed, detail="需要人群/渠道/预算三要素"
    )
```

注册后即可在 YAML 里用 `{type: has_action}`。

## 失败处理

- 断言内部抛异常 → 记为失败，detail 包含异常类型与消息（不会中断整个套件）
- 未知断言类型 → 记为失败，detail 说明类型名
- 适配器抛异常 → 记为失败，`type=adapter`

评测框架最怕"悄悄跳过"。宁可报错，不可沉默。

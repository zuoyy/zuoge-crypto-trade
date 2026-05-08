# TradePlanSignal AI 填写说明

这份文档给 AI/agent 组装 `TradePlanSignal` payload 使用。目标是让 AI 知道每个字段代表什么、从哪里取值、什么时候该填、什么时候不要填，以及哪些组合会被当前后端拒绝。

提交接口：

- agent 接口：`POST /api/v1/agent/proposals/signals`
- manual 接口：`POST /api/v1/manual/proposals/signals`
- 请求体就是一个 `TradePlanSignal`
- `signal_id`、`proposal_id`、`trace_id`、`status`、`inserted_at`、`updated_at` 都是系统生成或返回字段，不要放进请求体

## 1. AI 组装顺序

AI 不要直接从策略观点跳到 payload。按这个顺序填：

1. 读取最新交易上下文：`/api/v1/agent/trading-context?symbol=...&side=...`
2. 从上下文确认账户权益、可用资金、持仓、同标的冷却、风险限制和行情时间。
3. 判断 `position_intent`：开仓、加仓、接管、反手、平仓，或者放弃提交。
4. 先定入场参考价，再定止损，再定止盈；这样才能校验方向、风险和盈亏比。
5. 根据风险预算或目标名义金额填写 `sizing`。
6. 最后填写保护约束：滑点、行情新鲜度、最小盈亏比。

如果上下文显示冷却中、反向持仓冲突、敞口超限、杠杆不合规、行情过旧或没有明确止损，不要硬凑 payload，应当拒绝或等待。

## 2. 通用填写规则

- 时间统一使用 ISO 8601 UTC，例如 `2026-04-25T10:00:00Z`。
- 所有价格、金额、数量、比例都用 JSON number。
- 百分比字段用小数表达：`0.02` 表示 2%，`0.003` 表示 0.3%。
- `symbol` 使用交易所合约符号，例如 `BTCUSDT`；后端会转大写。
- 枚举字段用本文列出的英文固定值；后端会裁剪空格并转小写。
- `evidence` 里的空字符串会被丢弃，最终至少要剩 1 条。
- `expires_at` 必须晚于 `created_at`，并且提交时仍然在未来。
- 不要提交未知控制字段，例如 `strategy_revision`、`allowed_order_types`、`submission_channel`。

## 3. 顶层字段

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `context_version` | 否 | 交易上下文版本，用于审计 payload 基于哪次上下文生成。 | 如果刚读取了 trading-context，就把响应里的 `context_version` 原样填入；没有就省略。提交脚本会尝试自动补。 |
| `source` | 是 | 信号来源。 | 固定填 `Hermes`。 |
| `skill_name` | 是 | 生成信号的 skill 名。 | 固定填 `zuoge-crypto-trade`。 |
| `skill_version` | 是 | skill/prompt/策略封装版本。 | 填当前生成器版本，例如 `1.0.0`。不能为空。 |
| `symbol` | 是 | 要交易的币安合约标的。 | 填如 `BTCUSDT`、`ETHUSDT`。只提交系统和交易所可执行的合约。 |
| `side` | 是 | 新交易计划方向。 | 只能填 `long` 或 `short`。反手时填反手后的新方向。 |
| `confidence` | 是 | AI 对这笔计划的置信度。 | `0..1`，例如 `0.72`。低于系统阈值会被风控拒绝。 |
| `signal_reason` | 是 | 人类可读的核心交易理由。 | 用一句简洁中文说明为什么现在可以交易，避免空泛词。 |
| `evidence` | 是 | 支撑理由的证据列表。 | 至少 1 条，每条写具体证据，例如结构、成交量、关键价位、风险条件。 |
| `created_at` | 是 | payload 生成时间。 | 当前 UTC 时间。不要用本地时区字符串。 |
| `expires_at` | 是 | 信号有效期截止时间。 | 通常比 `created_at` 晚 10-30 分钟；高频触发更短。 |
| `position_intent` | 否 | 账户感知后的仓位意图。 | 推荐显式填写，取值见下一节。 |
| `replace_existing_position` | 否 | 是否允许新计划替换已有 owner runtime。 | 只有 `position_intent=reverse` 时必须为 `true`。其他场景通常省略或 `false`。 |
| `takeover_reason` | 否 | 接管/反手/平仓原因。 | `takeover`、`reverse`、`close` 时可填中文审计说明；普通 `open` 不填。 |
| `trade_params` | 是 | 完整交易计划。 | 必须包含 `entry`、`exits`、`sizing`、`position_management`、`execution_constraints`。 |

## 4. position_intent 怎么判断

`position_intent` 只能是：

- `open`：开新仓，或在已有同向仓位上明确加仓。
- `takeover`：不新增仓位，只用新计划接管已有同向仓位的止损、止盈、追踪止损等运行时管理。
- `reverse`：已有反向仓位，先处理旧方向，再开新方向。
- `close`：关闭已有同向目标仓位。

填写规则：

- 无当前标的仓位时，通常填 `open`。
- 有同向仓位且想加仓时，填 `open`，同时 `position_management.allow_add_position=true`，并设置合理 `max_add_count`。
- 有同向仓位且不想加仓、只想更新管理计划时，填 `takeover`。
- 有反向仓位且策略明确要求反手时，填 `reverse`，并且 `replace_existing_position=true`。
- 有反向仓位但没有明确反手意图时，不要提交。
- 想平掉当前方向时，填 `close`；如果没有对应持仓会被拒绝。

如果省略 `position_intent`，后端会结合持仓做推断：无仓位按开仓处理，同向持仓倾向接管，反向持仓会拒绝。AI 生成时建议显式填写，避免意图含糊。

## 5. trade_params 总结构

```json
"trade_params": {
  "entry": {},
  "exits": {},
  "sizing": {},
  "position_management": {},
  "execution_constraints": {}
}
```

当前 AI 默认不要提交 `margin`。Go 后端结构支持可选 `margin`，但当前 schema/template 口径默认省略；省略时系统会在开仓/反手场景使用运行时默认杠杆。

如果调用链明确允许提交 `margin` 且必须指定杠杆，只能使用：

```json
"margin": {
  "mode": "cross",
  "leverage": 2
}
```

限制：

- `mode` 只能是 `cross`；`isolated` 会被当前校验拒绝。
- `leverage` 只支持 `position_intent=open` 或 `position_intent=reverse`。
- `leverage` 必须在系统风险限制 `min_leverage..max_leverage` 内。

## 6. entry 入场计划

`entry` 描述什么时候触发、用什么订单类型、有效多久。

```json
"entry": {
  "trigger": {
    "type": "breakout",
    "trigger_price": 63520
  },
  "price": {
    "order_type": "limit",
    "limit_price": 63540,
    "acceptable_range": {
      "min": 63520,
      "max": 63620
    }
  },
  "timing": {
    "expire_after_seconds": 900
  }
}
```

### 6.1 entry.trigger

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `type` | 是 | 入场触发方式。 | 只能填 `immediate`、`touch_price`、`breakout`、`pullback_into_range`。 |
| `trigger_price` | 条件必填 | 单一触发价。 | `touch_price` 或 `breakout` 时必填，必须大于 0。 |
| `trigger_range.min` | 条件必填 | 回踩触发区间下沿。 | `pullback_into_range` 时必填，必须大于 0 且小于 `max`。 |
| `trigger_range.max` | 条件必填 | 回踩触发区间上沿。 | `pullback_into_range` 时必填，必须大于 `min`。 |

触发方式选择：

- `immediate`：策略认为当前价即可进入；仍然要提供价格保护。
- `touch_price`：价格触碰某个价位才进入。
- `breakout`：突破关键价位后进入。
- `pullback_into_range`：回踩到一个价格区间内进入。

### 6.2 entry.price

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `order_type` | 是 | 入场订单类型。 | 只能填 `market` 或 `limit`。 |
| `limit_price` | 条件必填 | 限价单价格。 | `order_type=limit` 时必填，必须大于 0。 |
| `acceptable_range.min` | 条件必填 | 可接受成交价下沿。 | 和 `acceptable_range.max` 成对填写，必须大于 0。 |
| `acceptable_range.max` | 条件必填 | 可接受成交价上沿。 | 必须大于 `min`。 |

价格保护必须至少满足一个：

- 填 `entry.price.acceptable_range`
- 或填正数 `execution_constraints.max_slippage_pct`

方向性规则：

- `side=long` 时，`limit_price` 不能高于 `acceptable_range.max`。
- `side=short` 时，`limit_price` 不能低于 `acceptable_range.min`。

### 6.3 entry.timing

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `expire_after_seconds` | 是 | 入场等待时长。 | 必须大于 0。常用 300、600、900、1800。 |

这个字段控制 pending entry 的最长等待时间。它不是整个 signal 的过期时间；整个 signal 仍由顶层 `expires_at` 控制。

## 7. exits 退出计划

`exits` 必须包含 4 组：`stop_loss`、`take_profit`、`trailing_stop`、`time_stop`。

```json
"exits": {
  "stop_loss": {},
  "take_profit": {},
  "trailing_stop": {},
  "time_stop": {}
}
```

### 7.1 stop_loss

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `mode` | 是 | 止损模式。 | `price`、`percent`、`none` 三选一。 |
| `stop_price` | 条件必填 | 固定止损价。 | `mode=price` 时必填，必须大于 0。 |
| `loss_pct` | 条件必填 | 按入场价计算的最大亏损比例。 | `mode=percent` 时必填，必须大于 0；例如 `0.015` 表示 1.5%。 |

AI 默认应提供止损。只有明确平仓或特殊策略场景才考虑 `mode=none`。`sizing.mode=risk_budget` 不能搭配 `stop_loss.mode=none`。

方向性规则：

- `side=long` 且 `mode=price` 时，`stop_price` 必须低于入场参考价。
- `side=short` 且 `mode=price` 时，`stop_price` 必须高于入场参考价。

入场参考价的优先级是：`limit_price` -> `trigger_price` -> `acceptable_range` 中点 -> `trigger_range` 中点。

### 7.2 take_profit

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `mode` | 是 | 止盈模式。 | `fixed_price`、`ladder`、`none` 三选一。 |
| `targets[].price` | 条件必填 | 止盈目标价。 | `fixed_price` 或 `ladder` 时必填，必须大于 0。 |
| `targets[].close_ratio` | 条件必填 | 到达该目标后平掉的仓位比例。 | 必须大于 0；所有 target 总和不能超过 1。 |

`fixed_price`：

- `targets` 必须正好 1 条。
- `close_ratio` 必须等于 `1`。
- 适合一次性全平。

`ladder`：

- `targets` 至少 1 条。
- 所有 `close_ratio` 总和小于等于 `1`。
- `position_management.allow_partial_exit` 必须为 `true`。
- `side=long` 时目标价必须全部高于入场参考价，且多目标价格递增。
- `side=short` 时目标价必须全部低于入场参考价，且多目标价格递减。

`none`：

- 不提供目标价。
- 如果设置了 `min_reward_risk`，没有止盈目标会导致盈亏比无法通过。

### 7.3 trailing_stop

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `enabled` | 是 | 是否启用追踪止损。 | `true` 或 `false`。 |
| `activation_mode` | 条件必填 | 追踪止损何时启动。 | `enabled=true` 时必填：`immediate`、`after_profit_pct`、`after_tp_hit`。 |
| `activation_profit_pct` | 条件必填 | 盈利达到多少比例后启动。 | `activation_mode=after_profit_pct` 时必填，必须大于 0。 |
| `trail_mode` | 条件必填 | 追踪距离模式。 | `enabled=true` 时必填：`percent` 或 `price_delta`。 |
| `trail_value` | 条件必填 | 追踪距离。 | `enabled=true` 时必填，必须大于 0。 |
| `step_mode` | 否 | 止损移动方式。 | 可省略，或填 `continuous`、`step`。 |
| `step_value` | 条件必填 | 阶梯移动步长。 | `step_mode=step` 时必填，必须大于 0。 |
| `move_to_break_even` | 否 | 启动后是否允许把止损推到保本附近。 | 需要保本保护时填 `true`，否则省略或 `false`。 |

如果不启用追踪止损，最小写法是：

```json
"trailing_stop": {
  "enabled": false
}
```

### 7.4 time_stop

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `enabled` | 是 | 是否启用时间止损/超时退出。 | `true` 或 `false`。 |
| `max_holding_minutes` | 条件必填 | 最长持仓分钟数。 | `enabled=true` 时必填，必须大于 0。 |

如果不启用，最小写法是：

```json
"time_stop": {
  "enabled": false
}
```

## 8. sizing 仓位大小

`sizing` 是正式下单规模请求，不是备注。

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `mode` | 是 | 仓位计算模式。 | `target_notional`、`risk_budget`、`fixed_quantity` 三选一。 |
| `target_notional` | 条件必填 | 目标名义金额。 | `mode=target_notional` 时必填，必须大于 0。 |
| `target_risk_amount` | 条件必填 | 本次愿意亏损的账户金额。 | `mode=risk_budget` 时必填，必须大于 0。 |
| `target_quantity` | 条件必填 | 目标币数量/合约数量。 | `mode=fixed_quantity` 时必填，必须大于 0。 |
| `min_notional` | 否 | 可接受最小名义金额。 | 用于表达太小就不值得做；必须大于 0。 |
| `max_notional` | 否 | 可接受最大名义金额。 | 用于限制风控裁剪后的上限；必须大于 0。 |
| `min_quantity` | 否 | 可接受最小数量。 | 必须大于 0。 |
| `max_quantity` | 否 | 可接受最大数量。 | 必须大于 0。 |
| `allow_downsize` | 否 | 是否允许系统缩量执行。 | 风控可能裁剪时建议 `true`；必须满额才有意义时填 `false`。 |

模式选择：

- `target_notional`：AI 已决定这笔做多少 USDT 名义金额。最直观，适合固定金额下单。
- `risk_budget`：AI 只决定最多亏多少钱，系统按入场价和止损距离反推名义金额。必须有可计算止损。
- `fixed_quantity`：AI 已决定币数量。只有在数量来自明确上游策略时使用。

范围规则：

- `min_notional <= max_notional`
- `min_notional <= target_notional`
- `target_notional <= max_notional`
- `min_quantity <= max_quantity`
- `min_quantity <= target_quantity`
- `target_quantity <= max_quantity`

风险提醒：

- `risk_budget` 需要入场参考价和止损价都可计算。
- 计算后的下单金额还会受账户权益、单笔上限、单标敞口、总敞口限制。
- 如果当前已有同向仓位，`open` 表示加仓，风险和执行阶段还会检查加仓限制。

## 9. position_management 仓位管理

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `allow_add_position` | 是 | 已有同向仓位时是否允许继续加仓。 | 普通开仓默认 `false`；明确加仓才填 `true`。 |
| `max_add_count` | 是 | 最多允许的加仓次数/同向活跃计划数量控制。 | `allow_add_position=false` 时必须为 `0`；允许加仓时填非负整数。 |
| `allow_partial_exit` | 是 | 是否允许分批止盈/部分平仓。 | `take_profit.mode=ladder` 时必须 `true`。 |
| `allow_reverse_on_opposite_signal` | 是 | 运行时遇到反向信号时是否允许反手处理。 | 默认 `false`。不要把它当作当前 payload 的反手授权；当前反手仍要用顶层 `position_intent=reverse`。 |
| `same_symbol_cooldown_minutes` | 是 | 当前计划完全退出后，同标的进入冷却多久。 | 非负整数。短线常用 30-90；不需要冷却填 `0`。 |

关键区别：

- `position_intent=reverse` 是当前这笔 payload 的反手意图。
- `allow_reverse_on_opposite_signal` 是这笔计划未来运行时遇到相反信号的策略偏好。
- `same_symbol_cooldown_minutes` 在计划退出后写入 runtime；冷却未结束时，同标的新开仓通常会被拒绝。

## 10. execution_constraints 执行约束

| 字段 | 必填 | 含义 | AI 怎么填 |
| --- | --- | --- | --- |
| `max_slippage_pct` | 条件必填 | 最大可接受滑点比例。 | 如果没有 `acceptable_range`，这里必须填正数。可填 `0.001..0.005` 等。 |
| `min_reward_risk` | 否 | 最小盈亏比要求。 | 例如 `1.5` 表示止盈距离至少是止损距离的 1.5 倍。 |
| `quote_staleness_seconds` | 否 | 允许使用的最大行情年龄。 | 非负整数。填 `0` 表示不额外限制；高频信号可填 5-15。 |

说明：

- 不支持 `allowed_order_types`；订单类型只由 `entry.price.order_type` 表达。
- `min_reward_risk` 使用第一个止盈目标和初始止损计算。
- 行情过旧时，风险评估可能触发 `market_data_freshness` 或 `quote_staleness_seconds` 拒绝。

## 11. 方向性价格校验

后端会用入场参考价检查止损和止盈方向。AI 必须先算清楚参考价：

1. 有 `entry.price.limit_price`，用它。
2. 否则有 `entry.trigger.trigger_price`，用它。
3. 否则有 `entry.price.acceptable_range`，用区间中点。
4. 否则有 `entry.trigger.trigger_range`，用区间中点。

`side=long`：

- `stop_loss.stop_price < 入场参考价`
- 所有 `take_profit.targets[].price > 入场参考价`
- ladder 目标价递增

`side=short`：

- `stop_loss.stop_price > 入场参考价`
- 所有 `take_profit.targets[].price < 入场参考价`
- ladder 目标价递减

## 12. 常见意图模板

无仓开多：

- `position_intent=open`
- `side=long`
- `allow_add_position=false`
- 必须有止损、止盈、价格保护、仓位大小

同向仓位接管：

- `position_intent=takeover`
- `side` 填当前持仓方向
- 不新增仓位，主要更新退出计划
- `takeover_reason` 写清为什么要接管，例如“原计划止损过宽，更新为新结构低点”

同向仓位加仓：

- `position_intent=open`
- `side` 填当前持仓方向
- `allow_add_position=true`
- `max_add_count` 大于 0
- 仍需满足敞口、加仓次数、冷却和行情限制

反手：

- `position_intent=reverse`
- `side` 填新方向
- `replace_existing_position=true`
- `takeover_reason` 写清反手依据
- 仍需满足新方向开仓的入场、止损、仓位、杠杆和敞口限制

平仓：

- `position_intent=close`
- `side` 填要关闭的持仓方向
- 如果当前没有对应方向持仓会被拒绝

## 13. 最小可用示例

这是“无仓开多 + 突破限价入场 + 梯度止盈 + 风控可缩量”的常用形态：

注意：示例里的 `created_at` 和 `expires_at` 只演示格式。实际提交时必须替换为当前 UTC 时间和仍在未来的过期时间，不能直接复制示例时间。

```json
{
  "context_version": "ctx_20260425100000",
  "source": "Hermes",
  "skill_name": "zuoge-crypto-trade",
  "skill_version": "1.0.0",
  "symbol": "BTCUSDT",
  "side": "long",
  "confidence": 0.82,
  "signal_reason": "15 分钟整理区间放量上破，回踩风险可由区间下沿控制",
  "evidence": [
    "价格突破 63520 阻力位后维持在区间上方",
    "突破 K 线成交量高于近 20 根均量",
    "止损放在 62980 后，第一目标盈亏比大于 1.5"
  ],
  "created_at": "2026-04-25T10:00:00Z",
  "expires_at": "2026-04-25T10:30:00Z",
  "position_intent": "open",
  "replace_existing_position": false,
  "trade_params": {
    "entry": {
      "trigger": {
        "type": "breakout",
        "trigger_price": 63520
      },
      "price": {
        "order_type": "limit",
        "limit_price": 63540,
        "acceptable_range": {
          "min": 63520,
          "max": 63620
        }
      },
      "timing": {
        "expire_after_seconds": 900
      }
    },
    "exits": {
      "stop_loss": {
        "mode": "price",
        "stop_price": 62980
      },
      "take_profit": {
        "mode": "ladder",
        "targets": [
          {
            "price": 63850,
            "close_ratio": 0.3
          },
          {
            "price": 64200,
            "close_ratio": 0.3
          },
          {
            "price": 64800,
            "close_ratio": 0.4
          }
        ]
      },
      "trailing_stop": {
        "enabled": true,
        "activation_mode": "after_profit_pct",
        "activation_profit_pct": 0.01,
        "trail_mode": "percent",
        "trail_value": 0.005,
        "step_mode": "continuous",
        "move_to_break_even": true
      },
      "time_stop": {
        "enabled": true,
        "max_holding_minutes": 240
      }
    },
    "sizing": {
      "mode": "target_notional",
      "target_notional": 1000,
      "min_notional": 500,
      "max_notional": 1000,
      "allow_downsize": true
    },
    "position_management": {
      "allow_add_position": false,
      "max_add_count": 0,
      "allow_partial_exit": true,
      "allow_reverse_on_opposite_signal": false,
      "same_symbol_cooldown_minutes": 60
    },
    "execution_constraints": {
      "max_slippage_pct": 0.003,
      "min_reward_risk": 1.5,
      "quote_staleness_seconds": 15
    }
  }
}
```

## 14. 提交前自检清单

AI 输出最终 payload 前逐项检查：

- 顶层没有 `signal_id`、`proposal_id`、`trace_id`、`status`、`strategy_revision`、`allowed_order_types`。
- `source=Hermes`，`skill_name=zuoge-crypto-trade`。
- `symbol` 是可交易合约，`side` 是 `long` 或 `short`。
- `confidence` 在 `0..1`，且不低于策略愿意提交的最低置信度。
- `signal_reason` 非空，`evidence` 至少 1 条非空证据。
- `created_at`、`expires_at` 是 UTC，且 `expires_at` 仍在未来。
- `position_intent` 与当前仓位一致；反手必须有 `replace_existing_position=true`。
- `entry` 有触发条件、订单类型、有效期和价格保护。
- `stop_loss` 可计算；`risk_budget` 不搭配 `stop_loss.mode=none`。
- 多头止损低于入场参考价，止盈高于入场参考价；空头相反。
- ladder 止盈方向正确，`close_ratio` 总和不超过 `1`。
- `sizing` 目标字段与 `mode` 匹配，并且 min/max 范围不冲突。
- `allow_add_position=false` 时 `max_add_count=0`。
- `take_profit.mode=ladder` 时 `allow_partial_exit=true`。
- `execution_constraints` 非负，并且 `acceptable_range` 或 `max_slippage_pct` 至少有一个。

## 15. 最简口径

AI 只需要记住：

- 顶层字段描述“谁、何时、交易什么、方向是什么、为什么交易”。
- `position_intent` 描述这笔计划和当前持仓的关系。
- `entry` 描述何时入场，`exits` 描述如何退出，`sizing` 描述做多大。
- `position_management` 描述持仓运行时的加仓、部分退出、反向处理和冷却策略。
- `execution_constraints` 描述执行前必须满足的滑点、盈亏比和行情新鲜度。
- 不确定是否合规时，不要硬填；先用最新 trading-context 降低规模、等待，或拒绝提交。

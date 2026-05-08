# 候选池清洗 + 结构优先强化记录（2026-05）

本次在 `/Users/zuo/.hermes/automation/crypto-trader-workflow/` 做了两类高价值强化，重点不是“多出单”，而是提高候选纯度与结构质量。

## 1. 候选池先做噪音清洗

更新文件：

- `scripts/crypto_collect_candidates.py`
- `scripts/crypto_filter_tradable.py`

### 新增 collect 层门禁

先在采集阶段剔除明显不可执行噪音：

- 非英文大写 / 数字的 symbol
- 中文名、emoji、空格、特殊字符 symbol
- 过短或异常长度 symbol
- `BTC` / `ETH` / `USD` / `USDT` 这类泛化基底词

### 新增 quality tags / penalty

对候选增加：

- `quality_tags`
- `quality_penalty`
- `quality_reasons`

当前已纳入惩罚或阻断的信号：

- `wash_trading`
- `insider wash trading`
- `smart money remove holdings`
- `paid promo`
- `negative sentiment`
- `mintable`
- 前十持仓过度集中
- 流动性偏薄

### filter 层进一步收紧

新增/收紧：

- `MIN_LIQUIDITY = 250000`
- `MIN_MARKET_CAP = 20000000`
- `MAX_QUALITY_PENALTY = 25.0`
- 命中 `wash_trading / smart_money_outflow / paid_promo / holder_concentration_high` 直接拒绝

## 2. 计划层从“现价模板”向“结构锚点”推进

更新文件：

- `scripts/crypto_generate_plans.py`

### 新增结构锚点概念

新增：

- `structure_reference_levels()`
- `refine_trade_levels()`
- `resolve_entry_zone()`

从 `5m/15m candle_features` 中显式读取：

- `trigger_5m`
- `invalidation_5m`
- `trigger_15m`
- `invalidation_15m`
- `trigger_distance_5m`
- `trigger_distance_15m`

核心变化：

- entry 不再默认围绕 `mark_price`
- stop 不再只靠波动宽度模板
- target 会根据结构失效点重算，避免 RR 只是模板算出来

### 结构距离硬门槛

新增：

- `MAX_DISTANCE_FROM_BREAKOUT_PCT = 1.4`
- `too_far_from_trigger`

用途：

- 如果价格已经离触发位太远，就算方向对，也不允许把“已走完一段”的行情硬包装成新机会
- 重点收紧：
  - `accepted_breakout`
  - `expansion_continuation`
  - `pullback_reaccept`
  - `trend_pressure_build`

## 3. 本次验证结果

dry-run：

```bash
python3 scripts/run_crypto_pipeline.py --dry-run
```

关键变化：

- `candidate_count`: `123 -> 87`
- collect 阶段额外剔除 `23` 个明显噪音 symbol
- filter 仍保留 `12`
- plan 仍为 `0`

这不是坏结果。

说明：

- 系统更能接受空仓
- 没有为了出单放松结构标准
- 当前瓶颈已从“候选太脏”转向“真正满足结构与盘口条件的标的太少”

## 4. 经验结论

最重要的结论：

> 先清噪音，再谈结构；先锚失效点，再谈 RR。

如果系统还在把中文 meme、付费推广、洗盘标的送进 plan 层，那么后面的结构判断会被无意义消耗。

如果 entry / stop 仍围绕现价模板，而不是围绕 trigger / invalidation，那么系统仍然只是“像交易”，不是真正按结构交易。

## 5. 下一步明确方向

下一批应继续强化：

1. `neutral_probe` 再收紧，尽量降级成观察名单
2. 增加更明确的结构标签：
   - `breakout_retest_hold`
   - `sweep_then_reclaim`
   - `range_reclaim`
   - `failed_break_reversal`
3. 把 HTF 从加分项继续推向更强硬门槛

原则不变：

- 无结构，不交易
- 无失效点，不开仓
- 空仓也是决策

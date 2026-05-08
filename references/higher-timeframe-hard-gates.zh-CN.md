# 1h/4h 高周期硬过滤升级记录

本次在 `/Users/zuo/.hermes/automation/crypto-trader-workflow/` 中，继续在既有 `5m/15m` 结构层之上接入 `1h/4h` 高周期框架，用于把系统从“小周期触发器”推向“多周期结构过滤器”。

## 新增数据接入

在 `shared/crypto_workflow.py` 的 `fetch_exchange_metrics()` 中新增：

- `GET /fapi/v1/klines?interval=1h&limit=48`
- `GET /fapi/v1/klines?interval=4h&limit=30`

并扩展：

- `candles.1h`
- `candles.4h`
- `candle_features.1h`
- `candle_features.4h`

## 新增高周期特征

延续既有 K 线特征生成逻辑，但提高了 `lookback` / `avg_window`：

- `trend_return_pct`
- `breakout_above_recent_high`
- `breakdown_below_recent_low`
- `distance_from_recent_high_pct`
- `distance_from_recent_low_pct`
- `inside_range`

理解方式：

- `trend_return_pct`：高周期方向是否顺势
- `breakout_*`：是否已经真正突破高周期关键位
- `distance_from_recent_*_pct`：距离关键位有多远，避免只看布尔值
- `inside_range`：是否还被困在高周期区间内部

## 计划生成侧接法

在 `scripts/crypto_generate_plans.py` 的 `evaluate_symbol_now()` 中新增 state：

- `breakout_1h`
- `breakout_4h`
- `trend_1h`
- `trend_4h`
- `distance_1h`
- `distance_4h`
- `inside_1h`
- `inside_4h`

并把这些变量纳入 `structure_score`：

- `breakout_score` 现在包含 `1h/4h`
- `trend_score` 现在包含 `1h/4h`
- 新增 `htf_alignment_score`

当前实现仍是“高周期强加权过滤”，还不是完全的“高周期硬门槛”。

## 阶段判定侧接法

`evaluate_stage()` 现在会把以下内容写入 `stage_reasons`：

- `4h关键位已突破`
- `1h关键位已突破`
- `4h趋势同向`
- `1h趋势同向`
- `4h仍在区间内`
- `1h临近区间边缘`

并把高周期方向纳入阶段触发约束，例如：

- `sweep_reclaim` 需要 `trend_1h > 0 or trend_4h > 0`
- `accepted_breakout` 需要 `breakout_1h / breakout_4h`，或至少 `trend_1h > 0 and not inside_1h`
- `pullback_reaccept` 需要 `trend_1h > 0`
- `trend_pressure_build` 需要 `trend_1h > 0 or breakout_1h`

## 证据输出新增字段

`evidence` 已增加：

- `breakout_1h`
- `breakout_4h`
- `trend_1h`
- `trend_4h`
- `distance_1h`
- `distance_4h`
- `inside_1h`
- `inside_4h`

复盘时可以直接看出：

- 这笔机会是否真正顺高周期
- 还是只是被 HTF 加权推高了分数

## 实测结果

使用已有 run dry-run 验证：

```bash
python3 scripts/run_crypto_pipeline.py --run-id 20260505-152734 --dry-run
```

结果从：

- `plan_count = 0`

提升到：

- `plan_count = 2`
- `opportunity_result_count = 2`
- `management_result_count = 0`

出现的新机会单：

- `ONDOUSDT long`
- `SPXUSDT long`

## 关键观察

这次升级证明 `1h/4h` 已经实际影响结果，而不只是写在 evidence 里。

但也暴露了一个新问题：

- 有些计划虽然 `setup_score` 很高
- 但 `stage_name` 仍然停留在 `neutral_probe`
- 最终导致“高分 + 弱标签 + 保守逻辑”的不匹配

典型症状：

- `ONDOUSDT` / `SPXUSDT` 都进入机会单
- 但 `stage_name=neutral_probe`
- `logic` 仍然是“结构勉强够用，只允许轻仓试错”

这说明 HTF 当前更多是“加分项”，还没有完全升级成“硬门槛 + 明确 setup 分类器”。

## 下次继续时的明确方向

优先做这两件事：

1. **收紧 `neutral_probe` 漏斗**
   - 提高 `neutral_probe` 的容忍门槛
   - 避免高分但无明确结构标签的计划流入机会单

2. **把 HTF 从加分项改成硬过滤条件**
   - 逆 `4h` 不开
   - `1h` 仍在区间中部不追
   - 只有高周期顺势、且临近边界或已脱离区间，才允许新开仓

一句话：

> 高周期现在已经参与决策了，但还没真正掌控开仓权。下一步要让 `1h/4h` 决定“能不能做”，而不只是决定“加几分”。

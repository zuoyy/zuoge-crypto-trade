# 多周期价格结构增强记录

本次在 `/Users/zuo/.hermes/automation/crypto-trader-workflow/` 的独立工作流中，为 `shared/crypto_workflow.py` 与 `scripts/crypto_generate_plans.py` 增加了不改 signal contract 的结构增强层。

## 已接入的数据

来自 Binance Futures 公共接口：

- `GET /fapi/v1/klines?interval=5m&limit=24`
- `GET /fapi/v1/klines?interval=15m&limit=16`

保留原有：

- premiumIndex
- openInterest
- ticker/bookTicker
- openInterestHist

## 新增结构特征

在 `fetch_exchange_metrics()` 中新增：

- `candles.5m`
- `candles.15m`
- `candle_features.5m`
- `candle_features.15m`

每个周期输出的关键字段：

- `recent_high`
- `recent_low`
- `range_expansion_ratio`
- `volume_expansion_ratio`
- `close_position_in_range`
- `body_to_range`
- `upper_wick_to_range`
- `lower_wick_to_range`
- `trend_return_pct`
- `breakout_above_recent_high`
- `breakdown_below_recent_low`

## 计划生成侧的接法

在 `evaluate_symbol_now()` 中把以下结构变量纳入 state 与 `structure_score`：

- `breakout_5m`
- `breakout_15m`
- `trend_5m`
- `trend_15m`
- `range_expansion_5m`
- `range_expansion_15m`
- `volume_expansion_5m`
- `volume_expansion_15m`
- `close_pos_5m`
- `close_pos_15m`
- `body_ratio_5m`
- `wick_support_5m`

方向处理规则：

- long 看 `breakout_above_recent_high`、`lower_wick_to_range`
- short 看 `breakdown_below_recent_low`、`upper_wick_to_range`
- short 的趋势与 close position 需要取反或转成方向一致的 bias 后再计分

## 阶段判定强化

`evaluate_stage()` 现在不只看 OI / funding / 盘口，还增加：

- 15m 是否已完成关键位突破
- 5m 是否刚完成触发
- 15m 趋势是否同向
- 5m 是否出现足够的波动/成交扩张
- 5m 收盘位置是否站在方向端
- 5m wick 是否体现扫损后收回/假突破修复

阶段约束更新示例：

- `accepted_breakout` 需要 `breakout_15m` 且 `close_pos_5m >= 0.62`
- `expansion_continuation` 需要 `range_expansion_5m >= 1.15` 且 `volume_expansion_5m >= 1.05`
- `pullback_reaccept` 需要 `trend_15m > 0` 且 `close_pos_5m >= 0.5`
- `sweep_reclaim` / `failed_breakout_reclaim` 增加 wick 回收要求

## 证据输出

`evidence` 现在额外输出：

- `breakout_5m`
- `breakout_15m`
- `trend_5m`
- `trend_15m`
- `range_expansion_5m`
- `volume_expansion_5m`
- `close_pos_5m`

这样复盘时可以直接看到结构层有没有真的参与决策，而不是只剩 OI / funding / book 指标。

## 验证结果

使用已有 run 直接重跑 dry-run：

```bash
python3 scripts/run_crypto_pipeline.py --run-id 20260505-152734 --dry-run
```

结果：

- collect: 132
- filter: 12
- plan: 0
- management: 2

说明：

- 新结构输入已成功接入整条流程
- 没有破坏现有 signal contract
- 当前批次没有达到新开仓标准，只输出仓位管理信号

## 重要结论

这个增强层属于“价格结构增强版”，不是“消息驱动增强版”。

仍缺：

- 外部新闻/公告/事件流
- liquidation cluster / taker flow
- 1h / 4h 更高周期结构框架

后续如果要继续提升高赔率 setup 识别，优先补：

1. `1h/4h` 多周期结构
2. 外部事件/新闻过滤
3. 更细粒度主动成交与爆仓流数据

# 候选标的筛选工作流补充：MVP 自动化落地

## 本次新增实现

围绕“热门/潜力币安合约 → 交易计划 → 推送交易系统”新增了一套最小闭环实现，代码位于：

- `workflow/shared/crypto_workflow.py`
- `workflow/scripts/crypto_collect_candidates.py`
- `workflow/scripts/crypto_filter_tradable.py`
- `workflow/scripts/crypto_generate_plans.py`
- `workflow/scripts/crypto_push_signals.py`
- `workflow/scripts/run_crypto_pipeline.py`
- `workflow/README-crypto-pipeline.md`

## 当前闭环能力

### 1. 候选采集
通过 Binance Web3 公共接口采集：
- Trending
- Top Search
- Alpha
- Social Hype
- Smart Money Inflow

### 2. 可交易过滤
只保留：
- Binance USDT-M 永续
- `status=TRADING`
- 有 Binance futures `exchangeInfo` 记录
- 基础流动性达到最小阈值

### 3. 账户接入
通过交易系统接口读取：
- `/api/v1/agent/account-context`
- `/api/v1/agent/trading-context`

用于把市场候选映射成“当前账户可考虑的候选”。

# 候选标的筛选工作流补充：MVP 自动化落地

## 本次新增实现

围绕“热门/潜力币安合约 → 交易计划 → 推送交易系统”新增了一套最小闭环实现，代码位于：

- `workflow/shared/crypto_workflow.py`
- `workflow/scripts/crypto_collect_candidates.py`
- `workflow/scripts/crypto_filter_tradable.py`
- `workflow/scripts/crypto_generate_plans.py`
- `workflow/scripts/crypto_push_signals.py`
- `workflow/scripts/run_crypto_pipeline.py`
- `workflow/README-crypto-pipeline.md`

## 当前闭环能力

### 1. 候选采集
通过 Binance Web3 公共接口采集：
- Trending
- Top Search
- Alpha
- Social Hype
- Smart Money Inflow

### 2. 可交易过滤
只保留：
- Binance USDT-M 永续
- `status=TRADING`
- 有 Binance futures `exchangeInfo` 记录
- 基础流动性达到最小阈值

### 3. 账户接入
通过交易系统接口读取：
- `/api/v1/agent/account-context`
- `/api/v1/agent/trading-context`

用于把市场候选映射成“当前账户可考虑的候选”，并且现在还能直接读取现有持仓清单。

### 4. 计划草案生成
当前 `crypto_generate_plans.py` 已从纯占位版，升级为“候选强度 + 账户适配 + Binance 盘口/OI/funding 过滤”的轻量结构评分器：
- 粗略方向推断
- 账户适配判断（`open / takeover / reverse`）
- OI 5m 变化过滤
- funding 过热过滤
- book ticker 盘口失衡过滤
- 动态止损 / 目标模板
- setup_score + RR 双门槛过滤
- 风险预算按账户权益约 0.65% 控制
- 最终只保留 top1~top2 计划
- 同时输出左哥格式交易卡片与 Telegram 卡片文件

### 5. 账户级持仓管理
除新机会计划外，系统现已额外输出 `position_management`：
- 针对真实持仓逐个生成动作建议
- 当前动作集合包括：`hold / reduce / takeover / close / reverse`
- 每个持仓给出独立卡片：动作、逻辑、当前仓位、保护位、依据
- 依据来自同一套交易所层数据：funding / OI 变化 / book imbalance

### 6. Signal 推送
通过 `zuoge-crypto-trade/scripts/submit_trade_plan_signal.py` 统一完成：
- payload 校验
- 自动补 `context_version`
- 推送到 `POST /api/v1/agent/proposals/signals`
- metadata 中附带 `setup_type / setup_score / expected_rr / trade_card / telegram_card / exchange_metrics`
- 根据 `position_intent` 自动生成差异化 `trade_params`：
  - `open` → immediate + market + risk_budget
  - `takeover` → pullback_into_range + limit + target_notional
  - `reverse` → breakout + market + `replace_existing_position=true`
  - `close` → touch_price + limit/fixed_quantity（已具备信号构造能力，待策略层触发）

## 运行验证
已实际执行多轮：

```bash
python3 workflow/scripts/run_crypto_pipeline.py --dry-run
```

最新结果说明：
- 候选采集、合约过滤、账户接入、signal 构建与 dry-run 推送链路均已打通
- 计划层已不再“为了出单而出单”，会主动回到空仓/零计划
- 当前可输出 Telegram-ready 卡片文件，位于每次 run 目录下的 `telegram-cards.txt`

## 动态计划合成补充

机会计划层已经从“先选 setup 再套参数”升级为“先读当前状态，再合成当前计划”。

当前机会计划主流程：

1. `evaluate_symbol_now()`：读取当前交易对的当下状态
   - mark price
   - spread
   - funding
   - OI 变化
   - book imbalance
   - volatility
   - momentum bias
   - account fit
   - risk budget
   - 当前 position intent

2. `evaluate_stage()`：先判定当前阶段，而不是先套策略标签
   - `sweep_reclaim`
   - `failed_breakout_reclaim`
   - `accepted_breakout`
   - `expansion_continuation`
   - `pullback_reaccept`
   - `trend_pressure_build`
   - `neutral_probe`

3. `decide_if_trade()`：如果当前阶段和实时条件不支持，直接拒绝，不强行出机会单
   - 典型拒绝原因：
     - `spread_too_wide`
     - `funding_too_hot`
     - `book_not_supporting`
     - `oi_contracting`
     - `stage_score_too_low`

4. `synthesize_trade_plan()`：根据这个 symbol 的当前状态与阶段，生成一次性的独立计划

5. `map_stage_to_setup()`：最后再给 setup 标签
   - `sweep_reclaim` -> `liquidity_sweep`
   - `failed_breakout_reclaim` -> `false_breakout_recovery`
   - `accepted_breakout` -> `breakout`
   - `expansion_continuation` -> `volatility_expansion`
   - `pullback_reaccept` -> `pullback_confirmation`
   - `trend_pressure_build` -> `breakout_continuation`
   - fallback -> `trend_continuation`

核心原则：
- 同一个交易对，在不同时间点，应该生成不同计划
- setup 标签是结果，不是起点
- 无结构，不交易；无失效点，不开仓；空仓也是决策

当前仍未覆盖：
- K 线级 price action
- swing high / low
- reclaim 关键位
- 多周期结构
- 消息驱动 / event catalyst

因此，现阶段应把它理解为“轻量状态机 + 动态计划合成器”，不是最终完整版。


这次最重要的学习不是“怎么获取更多热门币”，而是：

- 真正决定质量的是计划层，不是候选层
- OI / funding / depth 这类交易所层过滤必须前置，否则很容易把社交热度误判成可执行机会
- 系统应该接受 `plan_count=0`，空仓也是决策

## 后续强化优先级

按先后顺序建议：

1. 强化结构识别
   - 趋势延续
   - 突破
   - 假突破
   - 回踩确认
   - 流动性扫损回收

2. 加入更强过滤
   - OI
   - funding
   - depth
   - 量价扩张

3. 完善账户意图路由
   - `open`
   - `takeover`
   - `reverse`
   - `close`

## 使用提醒

当前这套实现应被视为：
- 可运行的 MVP 骨架
- 不是最终选币与交易计划系统

未来 agent 看到这套代码时，不要误以为它已经具备成熟的结构判断能力。真正应继续投入的地方是 `crypto_generate_plans.py`，不是推送层。

## 后续强化优先级

按先后顺序建议：

1. 强化结构识别
   - 趋势延续
   - 突破
   - 假突破
   - 回踩确认
   - 流动性扫损回收

2. 加入更强过滤
   - OI
   - funding
   - depth
   - 量价扩张

3. 完善账户意图路由
   - `open`
   - `takeover`
   - `reverse`
   - `close`

## 使用提醒

当前这套实现应被视为：
- 可运行的 MVP 骨架
- 不是最终选币与交易计划系统

未来 agent 看到这套代码时，不要误以为它已经具备成熟的结构判断能力。真正应继续投入的地方是 `crypto_generate_plans.py`，不是推送层。

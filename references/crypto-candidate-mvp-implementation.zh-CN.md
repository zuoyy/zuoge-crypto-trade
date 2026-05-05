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

用于把市场候选映射成“当前账户可考虑的候选”。

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

### 5. Signal 推送
通过 `zuoge-crypto-trade/scripts/submit_trade_plan_signal.py` 统一完成：
- payload 校验
- 自动补 `context_version`
- 推送到 `POST /api/v1/agent/proposals/signals`
- metadata 中附带 `setup_type / setup_score / expected_rr / trade_card / telegram_card / exchange_metrics`

## 运行验证
已实际执行多轮：

```bash
python3 workflow/scripts/run_crypto_pipeline.py --dry-run
```

最新结果说明：
- 候选采集、合约过滤、账户接入、signal 构建与 dry-run 推送链路均已打通
- 计划层已不再“为了出单而出单”，会主动回到空仓/零计划
- 当前可输出 Telegram-ready 卡片文件，位于每次 run 目录下的 `telegram-cards.txt`

## 关键结论

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

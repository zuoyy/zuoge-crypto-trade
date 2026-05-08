# 宏观/公告事件风险层接入记录

本次在 `/Users/zuo/.hermes/automation/crypto-trader-workflow/` 中，为独立候选发现与计划生成流程增加了一个**轻量事件风险层**。它的定位不是“消息交易引擎”，而是先做成**避雷层**：当公告直接点名标的，或出现明显风险词时，先降分或直接过滤。

## 接入点

### 1. `shared/crypto_workflow.py`
新增：

- `fetch_binance_support_announcements()`
- `build_event_risk_map(symbols)`

数据源：

- Binance support announcement 列表接口

核心输出：

- `risk_score`
- `tags`
- `matched_articles`
- `has_recent_event`

### 2. `scripts/crypto_collect_candidates.py`
在候选聚合后，为每个 candidate 附加：

- `event_risk`

这样后续 filter / plan 阶段不用再次单独抓取公告。

### 3. `scripts/crypto_filter_tradable.py`
新增硬过滤：

- `MAX_EVENT_RISK_SCORE = 2.5`

当 `event_risk.risk_score > 2.5` 时，直接拒绝：

- `reason = event_risk_too_high`

### 4. `scripts/crypto_generate_plans.py`
把以下字段接入 state：

- `event_risk`
- `event_risk_score`
- `event_tags`

同时：

- 在 `structure_score` 中增加事件惩罚：
  - `event_penalty = event_risk_score * 14.0`
- 在 `stage_reasons` 中追加：
  - `事件风险=<score>`
- 在 `evidence` 中追加：
  - `event_risk_score`
  - `event_tags`
- 在 `decide_if_trade()` 中增加硬门槛：
  - `event_risk_score >= 2.5 -> event_risk_too_high`

## 当前关键词体系

高风险：

- `DELIST`
- `DELISTING`
- `REMOVE`
- `SUSPEND`
- `MONITORING`
- `UNLOCK`

中低风险/催化提示：

- `MAINTENANCE`
- `LISTING`
- `LAUNCHPOOL`
- `LAUNCHPAD`
- `AIRDROP`
- `ROADMAP`

说明：

- 现在只做**风险识别与惩罚**，不是方向性解读
- 比如 `LISTING` 只记为“事件存在”，不会自动翻译成做多理由

## 验证方式

直接重跑 dry-run：

```bash
python3 scripts/run_crypto_pipeline.py --run-id 20260505-152734 --dry-run
```

在本次会话中，事件层加入后，整条流程依然能正常走完，且 signal contract 未被破坏。

## 重要结论

这个事件层当前更像：

- **避雷层**
- **公告触发风险过滤层**

还不是：

- 宏观事件时间窗过滤器
- Twitter / Telegram / 项目公告情绪层
- 真正的消息驱动方向交易模块

## 局限与下一步

当前仍缺：

1. 宏观时间窗
   - CPI
   - FOMC
   - 非农
   - 利率决议

2. 更广事件源
   - 项目官方公告
   - 上下架 / 解锁日历
   - 监管 / ETF / 宏观新闻

3. 方向化解释
   - 现在只知道“有事”或“有风险”
   - 还不知道“这条消息更偏多还是偏空，以及影响持续多久”

## 使用建议

如果用户要求：

- “先把明显会踩雷的币过滤掉”
- “把公告风险也纳入候选筛选”
- “不要只看图，先处理公告/下架/维护风险”

优先复用这层实现。

如果用户要求：

- “做消息驱动交易”
- “围绕 CPI / FOMC / 非农做时间窗控制”
- “把新闻直接转成方向偏向”

说明：当前实现不够，需要继续扩成**宏观事件时间窗层 + 多源新闻层**。

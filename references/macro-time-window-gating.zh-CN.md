# 宏观事件时间窗风控接入记录

## 适用范围

用于 `zuoge-crypto-trade` 下的独立工作流：

- `/Users/zuo/.hermes/automation/crypto-trader-workflow/scripts/crypto_collect_candidates.py`
- `/Users/zuo/.hermes/automation/crypto-trader-workflow/scripts/crypto_filter_tradable.py`
- `/Users/zuo/.hermes/automation/crypto-trader-workflow/scripts/crypto_generate_plans.py`
- `/Users/zuo/.hermes/automation/crypto-trader-workflow/shared/crypto_workflow.py`

## 本次新增能力

新增轻量宏观事件时间窗层，目标不是预测方向，而是在重大宏观窗口主动降低出手频率，必要时禁止新开仓。

核心实现：

1. `shared/crypto_workflow.py`
   - `load_macro_event_calendar(path: str | None = None)`
   - `current_macro_risk(calendar: list[dict] | None = None, now: datetime | None = None)`
2. 默认日历文件：
   - `config/macro_events.json`
3. 环境变量覆盖：
   - `CRYPTO_TRADER_MACRO_EVENTS_FILE`

## 当前规则

事件字段示例：

```json
{
  "name": "FOMC Rate Decision",
  "impact": "high",
  "start_time_utc": "2026-05-06T18:00:00Z",
  "pre_window_minutes": 180,
  "post_window_minutes": 180,
  "scope": "market"
}
```

权重：

- `low` → `0.4`
- `medium` → `1.0`
- `high` → `2.2`

阻断条件：

- `is_blocked = risk_score >= 2.0`

这意味着：

- 高影响宏观事件时间窗内：禁止新机会单
- 无 active window 时：只把未来事件写入上下文，不直接阻断

## 工作流接入点

### 1. collect 阶段

`crypto_collect_candidates.py`

- 调用 `current_macro_risk()`
- 把 `macro_risk` 写入顶层 payload
- 给每个 candidate 附带同一份 `macro_risk`

### 2. filter 阶段

`crypto_filter_tradable.py`

如果 `source["macro_risk"]["is_blocked"] == true`：

- 直接输出空的 `filtered`
- 全部候选写入 `rejected`
- 统一原因：`macro_event_window_blocked`

这样宏观窗口会在“可交易过滤层”被第一时间拦下。

### 3. plan 阶段

`crypto_generate_plans.py`

再次读取 `macro_risk`，如果仍为 blocked：

- `plans = []`
- 不生成新的 trade plan
- 但仍执行 `build_position_management(account_payload)`

关键原则：

- **宏观窗口阻断新开仓，不阻断已有仓位管理**

## 已验证结果

### A. 正常日历下

运行：

```bash
python3 scripts/run_crypto_pipeline.py --dry-run
```

观察到：

- collect 正常产出 `macro_risk`
- 当前无 active macro window 时，`is_blocked=false`
- filter / plan 不会被误伤

### B. 强制模拟 blocked 窗口

通过把某次 run 的 `candidates.json` 临时改成：

- `risk_score = 2.2`
- `is_blocked = true`
- `has_active_window = true`

再重跑：

```bash
python3 scripts/crypto_filter_tradable.py --run-id <RUN_ID>
python3 scripts/crypto_generate_plans.py --run-id <RUN_ID>
```

验证到：

- `filtered.json` → `kept_count = 0`, `macro_blocked = true`
- `trade-plans.json` → `plan_count = 0`, `macro_blocked = true`
- `position_management` 仍保留并正常输出

## 关键结论

这层不是“宏观做方向”，而是“宏观做风控”：

- 先看风险，再看机会
- 大事件时间窗里，允许空仓
- 系统应默认少做，而不是硬找单

## 当前局限

1. 事件源还是静态 JSON，不是自动经济日历抓取
2. 现在是全市场级阻断，没有细分美元流动性 / 加密原生 / 单币事件
3. 现在只有硬阻断，没有黄灯降级机制

## 推荐下一步

把宏观层升级成三档：

- `green`：正常运行
- `yellow`：只允许 A+ 结构 + 降仓位
- `red`：禁止新开仓，只保留仓位管理

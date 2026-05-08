---
name: zuoge-crypto-trade
description: Use this skill to generate, validate, and push Hermes trade-plan signals for the crypto-trader system, including trading-context reads, structured payload assembly, contract checks, and HTTP submission to the signal ingestion API. Do not use it for plain account, position-list, or trading-context queries.
---

# Zuoge Crypto Trade

## Architecture Role

`zuoge-crypto-trade` is the **hands** of the trading system. It assembles structured trade-plan payloads and submits them via HTTP to the signal ingestion API. It does NOT discover candidates, evaluate market structure, or decide when to trade — that is the responsibility of `crypto-trader-workflow` (strategy brain). `zuoge-crypto-query` is the eyes that reads state.

Signal submission from `crypto-trader-workflow`'s `crypto_push_signals.py` calls this skill's `scripts/submit_trade_plan_signal.py` directly. Do NOT route manual "what should I trade" questions here; they belong to the workflow brain.

## Overview

Use this skill when Hermes or OpenClaw needs to turn strategy analysis plus account and position context into a trade-plan signal for the crypto-trader backend.
This skill may read account or trading context as input to submission decisions.
For user-facing Chinese query-only replies, prefer `$zuoge-crypto-query` instead of this skill.

Typical requests:

- `根据当前账户状态生成一个 BTCUSDT 多头信号`
- `帮我组装 trade plan signal`
- `校验这个 payload 能不能提交`
- `提交这笔信号`

## Read Path

Start with [references/submit-quickstart.md](references/submit-quickstart.md).
Only open heavier references when needed:
- [references/trade-plan-signal-parameter-design.md](references/trade-plan-signal-parameter-design.md)
- [references/enums.md](references/enums.md)
- [references/payload-template.json](references/payload-template.json)
- [references/trade-plan-signal.schema.json](references/trade-plan-signal.schema.json)
- [references/ai-caller-guide.md](references/ai-caller-guide.md)
- [references/candidate-selection-workflow.zh-CN.md](references/candidate-selection-workflow.zh-CN.md)

## Candidate Selection Rule

Before generating any trade-plan signal from "热门币 / 潜力币 / 候选标的" requests, do not jump straight from a heat list to payload generation.
Use a staged workflow:

1. Build a candidate pool from heat / narrative / ranking sources.
2. Filter to Binance-executable perpetual contracts only.
3. Filter again by liquidity, volume expansion, and marketability.
4. Check account fit: current positions, total exposure, same-direction correlation, cooldown, and remaining risk budget.
5. Confirm market structure before planning the trade: trend continuation, breakout, false breakout recovery, pullback confirmation, liquidity sweep, or volatility expansion.
6. Only then generate the trade-plan payload and submit.

Hot does not equal tradable.
Potential does not equal executable.
If the symbol fails any filter above, reject or defer instead of forcing a signal.

## Execution

Use `scripts/submit_trade_plan_signal.py` to submit the final payload.
The helper script can fetch `/api/v1/agent/trading-context` and backfill `context_version` automatically.
Run the helper before submission whenever possible; it performs local contract checks before sending the request.

## Candidate-to-Signal Workflow

When the user wants Hermes to discover *hot or promising Binance futures contracts*, then generate full trade plans and push them to the crypto-trader backend, do **not** jump straight from a hot list to signal submission.

Use this five-layer gate before payload composition:

1. **Candidate discovery** — gather from trending / top-search / social-hype / smart-money / alpha sources.
2. **Binance futures tradability filter** — keep only Binance USDT-M perpetual contracts that are actually tradable and liquid enough.
3. **Flow + volatility filter** — distinguish social noise from real money and real expansion.
4. **Account-fit filter** — reject candidates that conflict with current exposure, position count, symbol cooldown, or same-theme concentration.
5. **Structure confirmation** — only then generate a trade plan if there is a clear invalidation point and target space.

Hard rule: **热门 ≠ 可交易，潜力 ≠ 可执行**. Never submit directly from a ranking endpoint.

A standalone implementation scaffold now exists at `/Users/zuo/.hermes/automation/crypto-trader-workflow/` with:
- `scripts/run_crypto_pipeline.py`
- `scripts/crypto_collect_candidates.py`
- `scripts/crypto_filter_tradable.py`
- `scripts/crypto_generate_plans.py`
- `scripts/crypto_push_signals.py`

Treat this as the isolated working area for crypto-trader signal automation. Prefer it over mixing new logic into the generic `hermes-agent/workflow/` tree.

## Defer Instead of Force

When the workflow finds structure that is interesting but not executable **now**, do not collapse everything into `rejected`.
Use layered outputs:

1. `plans` — executable now
2. `watchlist` — structure still valid but confirmation missing
3. `trigger_plans` — explicit activation criteria required before execution
4. `rejected` — genuinely invalid / low-quality / untradable

Prefer downgrade over discard for near-miss structures. This is especially important for a structure-first, high-RR workflow where many good trades begin as stalk setups rather than immediate market orders.

Downgrade these reasons before considering full rejection:
- `book_not_supporting`
- `directional_book_too_thin`
- `neutral_probe_too_weak`
- `inside_4h_range`
- `inside_1h_midrange`
- `neutral_probe_too_far_from_trigger`

When `plan_count == 0`, inspect `watchlist.json`, `trigger-plans.json`, and `rejection_stats` before concluding the run produced no useful output.

## Rescan-to-Push State Handoff

When the workflow uses `crypto_rescan_watchlist.py`, the rescanner must not stop at an analytical summary.
It should emit push-consumable state for the current run.

Required behavior:
1. Write `rescan-summary.json` with normalized buckets:
   - `promoted_plans`
   - `remaining_watchlist`
   - `remaining_trigger_plans`
   - `invalidated`
2. Also write current-run downstream artifacts so later stages do not depend on manual interpretation:
   - `watchlist.json` from `remaining_watchlist`
   - `trigger-plans.json` from `remaining_trigger_plans`
3. `crypto_push_signals.py` should prefer rescanned `promoted_plans` over stale original `plans`.
4. If the rescan run does not have its own `trade-plans.json`, push should fall back to the `source_run_id` plan artifact for shared context like `macro_risk`, `account_context`, and position-management decisions.

This keeps the run state machine coherent:
- original run discovers
- rescan run reclassifies
- push consumes current truth, not stale pre-rescan truth

## Pitfalls

- Do **not** let push read only `trade-plans.json` from the current rescan run. A pure rescan run may not have that file.
- Do **not** keep rescanner output as summary-only if downstream steps need executable state.
- `remaining_count` may count both watchlist and trigger-plan entries; if monitoring needs symbol-level backlog, add a distinct symbol count instead of assuming entry count == symbol count.

## Reference

- [references/submit-quickstart.md](references/submit-quickstart.md)
- [references/trade-plan-signal-parameter-design.md](references/trade-plan-signal-parameter-design.md) — AI-facing field-by-field payload guide aligned to the Go implementation
- [references/ai-caller-guide.md](references/ai-caller-guide.md)
- [references/trade-plan-signal.schema.json](references/trade-plan-signal.schema.json)
- [references/payload-template.json](references/payload-template.json)
- [references/candidate-selection-workflow.zh-CN.md](references/candidate-selection-workflow.zh-CN.md) — 当目标是从市场里找热门/潜力币安合约并进入交易计划流程时，先看这份筛选工作流
- [references/crypto-candidate-mvp-implementation.zh-CN.md](references/crypto-candidate-mvp-implementation.zh-CN.md) — 本次已落地的 MVP 自动化闭环、代码位置、验证结果与后续强化重点
- [references/structure-first-hardening-2026-05.zh-CN.md](references/structure-first-hardening-2026-05.zh-CN.md) — 候选池清洗 + 结构优先计划层强化记录：如何先剔除噪音标的，再把 entry/stop 锚到结构触发位与失效位，避免为了出单硬造机会
- [references/multi-timeframe-structure-upgrade.zh-CN.md](references/multi-timeframe-structure-upgrade.zh-CN.md) — 多周期价格结构增强记录：5m/15m K 线特征如何接入 state / stage / evidence，且不改 signal contract
- [references/higher-timeframe-hard-gates.zh-CN.md](references/higher-timeframe-hard-gates.zh-CN.md) — 1h/4h 高周期框架升级记录：如何把 HTF 从加分项提升为更强过滤层，并识别 neutral_probe 虚高分问题
- [references/output-hardening-2026-05.md](references/output-hardening-2026-05.md) — 输出层强化记录：如何把 plan/reject 二元结构升级为 executable + watchlist + trigger-plan + rejection-stats，并调整 neutral_probe 阈值与盘口观察逻辑
- [references/macro-time-window-gating.zh-CN.md](references/macro-time-window-gating.zh-CN.md) — 宏观事件时间窗风控接入记录：静态事件日历、active window 阻断、filter/plan 双层拦截，以及“新开仓阻断但仓位管理继续运行”的实现细节
- [references/watchlist-trigger-plan-upgrade-2026-05.md](references/watchlist-trigger-plan-upgrade-2026-05.md) — watchlist / trigger-plan 分层输出升级、验证结果与 neutral_probe 阈值陷阱
- [references/candidate-selection-workflow.zh-CN.md](references/candidate-selection-workflow.zh-CN.md)

---
name: zuoge-crypto-trade
description: Use this skill to generate, validate, and push Hermes trade-plan signals for the crypto-trader system, including trading-context reads, structured payload assembly, contract checks, and HTTP submission to the signal ingestion API. Do not use it for plain account, position-list, or trading-context queries.
---

# Zuoge Crypto Trade

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

## Reference

- [references/submit-quickstart.md](references/submit-quickstart.md)
- [references/trade-plan-signal-parameter-design.md](references/trade-plan-signal-parameter-design.md) — AI-facing field-by-field payload guide aligned to the Go implementation
- [references/ai-caller-guide.md](references/ai-caller-guide.md)
- [references/trade-plan-signal.schema.json](references/trade-plan-signal.schema.json)
- [references/payload-template.json](references/payload-template.json)
- [references/candidate-selection-workflow.zh-CN.md](references/candidate-selection-workflow.zh-CN.md) — 当目标是从市场里找热门/潜力币安合约并进入交易计划流程时，先看这份筛选工作流
- [references/crypto-candidate-mvp-implementation.zh-CN.md](references/crypto-candidate-mvp-implementation.zh-CN.md) — 本次已落地的 MVP 自动化闭环、代码位置、验证结果与后续强化重点
- [references/candidate-selection-workflow.zh-CN.md](references/candidate-selection-workflow.zh-CN.md)

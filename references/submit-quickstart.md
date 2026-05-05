# Submit Quickstart

Use this file first for TradePlanSignal composition and submission.

## When To Use

- generate a signal
- validate a trade payload
- submit a trade plan

Do not use this file for plain account or position queries.

## Required Read Path

1. Read the latest trading context.
2. Read this file.
3. Open `enums.md` only if you need exact enum literals.
4. Open `payload-template.json` only if you need a starting shape.
5. Open `trade-plan-signal.schema.json` only for final validation or unclear field requirements.

## Minimal Trading Context

Need these fields at minimum:

- `equity`
- `available_cash`
- `total_exposure`
- `open_positions`
- `symbol_position`
- `risk_limits`
- `position_runtime_state`
- `same_symbol_cooldown`

## Core Decisions

- no current position -> usually `position_intent=open`
- same-side position exists -> decide `open` vs `takeover`
- opposite-side position exists -> require explicit `reverse` or reject
- close intent with matching position -> `position_intent=close`
- cooldown, insufficient equity, or excess exposure -> reduce size or reject

## Hard Rules

- `source=Hermes`
- `skill_name=zuoge-crypto-trade`
- `side` must be `long` or `short`
- `confidence` must be within `0..1`
- `evidence` must contain at least one item
- use UTC ISO 8601 timestamps
- do not include `signal_id`, `proposal_id`, or `strategy_revision`
- `position_intent=reverse` requires `replace_existing_position=true`

## Top-Level Payload

- `source`
- `skill_name`
- `skill_version`
- `symbol`
- `side`
- `confidence`
- `signal_reason`
- `evidence`
- `created_at`
- `expires_at`
- `trade_params`

## Submit

- endpoint: `POST /api/v1/agent/proposals/signals`
- helper script: `scripts/submit_trade_plan_signal.py`

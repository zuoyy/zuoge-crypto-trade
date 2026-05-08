# Contract Alignment Notes for Crypto Push Signals

## Why this exists

This note captures a live correction from workflow integration: signal generation must align to the existing `zuoge-crypto-trade` contract exactly. Do not expand or reinterpret the form schema ad hoc.

## Hard contract lessons

- Keep `position_intent` strictly within the existing enum set:
  - `open`
  - `takeover`
  - `reverse`
  - `close`
- Do **not** invent new intents like `close-partial` or `full-exit`.
- Partial vs full close is expressed through sizing, not new enums:
  - partial close -> `position_intent=close` + `trade_params.sizing.mode=fixed_quantity` + `target_quantity < current position quantity`
  - full exit -> `position_intent=close` + `trade_params.sizing.mode=fixed_quantity` + `target_quantity = current position quantity`
- `reverse` must remain `position_intent=reverse` and must set `replace_existing_position=true`.
- `takeover` must remain `position_intent=takeover`; include `takeover_reason` when available.

## Required payload-shape reminders

- `trade_params.exits.targets[*]` must use `close_ratio`, not `size_pct`.
- `trade_params.exits` must include `trailing_stop`, even when disabled.
- `trade_params` must include `position_management`.
- Avoid non-schema fields such as:
  - top-level `metadata`
  - `trade_params.thesis`
  - `sizing.leverage`

## Verified workflow result

The standalone workflow at `/Users/zuo/.hermes/automation/crypto-trader-workflow/` now emits schema-aligned opportunity and management signals in `scripts/crypto_push_signals.py`.

Verified management mappings:

- `reduce` -> executable partial close using `position_intent=close` + partial `fixed_quantity`
- `close` -> executable full exit using `position_intent=close` + full `fixed_quantity`
- `reverse` -> executable reverse using `position_intent=reverse` + `replace_existing_position=true`
- `takeover` -> executable same-side takeover using `position_intent=takeover`

## Current limitation

This fixes signal-contract correctness, not full strategy coverage.
Current plan generation is still MVP-level and only classifies:

- `trend_continuation`
- `breakout_continuation`
- `pullback_confirmation`

Broader setup families mentioned in the skill/user trading style — such as false-breakout recovery, liquidity sweep, and standalone volatility-expansion plans — still need dedicated plan builders.

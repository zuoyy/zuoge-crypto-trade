# TradePlanSignal Enum Reference

## Purpose

This file centralizes all supported enum-like fields and fixed values for `zuoge-crypto-trade`.
AI callers should prefer this file when deciding what literal values are allowed in a payload.

## Fixed Top-Level Values

| Field | Allowed value(s) | Notes |
| --- | --- | --- |
| `source` | `Hermes` | Fixed literal required by the backend contract. |
| `skill_name` | `zuoge-crypto-trade` | Fixed literal required by the backend contract. |

## Top-Level Enums

| Field | Allowed value(s) | Notes |
| --- | --- | --- |
| `side` | `long`, `short` | Used by both strategy output and final signal. |
| `position_hint` | `open`, `takeover`, `reverse`, `close` | Optional strategy-side hint before normalization. |
| `position_intent` | `open`, `takeover`, `reverse`, `close` | Final account-aware intent for submission. |

## Trade Params Enums

| Field | Allowed value(s) | Notes |
| --- | --- | --- |
| `trade_params.entry.trigger.type` | `immediate`, `touch_price`, `breakout`, `pullback_into_range` | `touch_price` and `breakout` require `trigger_price`; `pullback_into_range` requires `trigger_range`. |
| `trade_params.entry.price.order_type` | `market`, `limit` | `limit` requires `limit_price`. |
| `trade_params.exits.stop_loss.mode` | `price`, `percent`, `none` | `price` requires `stop_price`; `percent` requires `loss_pct`. |
| `trade_params.exits.take_profit.mode` | `fixed_price`, `ladder`, `none` | When not `none`, provide at least one `targets` item. |
| `trade_params.exits.trailing_stop.activation_mode` | `immediate`, `after_profit_pct`, `after_tp_hit` | Required when trailing stop is enabled. |
| `trade_params.exits.trailing_stop.trail_mode` | `percent`, `price_delta` | Required when trailing stop is enabled. |
| `trade_params.exits.trailing_stop.step_mode` | `continuous`, `step` | Optional; `step` requires `step_value`. |
| `trade_params.sizing.mode` | `target_notional`, `risk_budget`, `fixed_quantity` | Requires one matching numeric target field. |
| `trade_params.margin.mode` | `cross` | Omit `margin` by default. `isolated` is rejected by current backend validation. |

## Context Enums

| Field | Allowed value(s) | Notes |
| --- | --- | --- |
| `symbol_position.side` | `long`, `short` | Current live position side from trading context. |
| `symbol_position.margin_type` | `cross`, `isolated` | Current margin mode from trading context. |
| `risk_context.side` | `long`, `short` | Side-scoped risk snapshot. |

## Conditional Requirements

- `position_intent=reverse` requires `replace_existing_position=true`.
- `trade_params.entry.trigger.type=touch_price` requires `trade_params.entry.trigger.trigger_price`.
- `trade_params.entry.trigger.type=breakout` requires `trade_params.entry.trigger.trigger_price`.
- `trade_params.entry.trigger.type=pullback_into_range` requires `trade_params.entry.trigger.trigger_range.min` and `trade_params.entry.trigger.trigger_range.max`.
- `trade_params.entry.price.order_type=limit` requires `trade_params.entry.price.limit_price`.
- `trade_params.exits.stop_loss.mode=price` requires `trade_params.exits.stop_loss.stop_price`.
- `trade_params.exits.stop_loss.mode=percent` requires `trade_params.exits.stop_loss.loss_pct`.
- `trade_params.exits.take_profit.mode=fixed_price` requires exactly one target with `close_ratio=1`.
- `trade_params.exits.take_profit.mode=ladder` requires `trade_params.position_management.allow_partial_exit=true`.
- `trade_params.exits.trailing_stop.enabled=true` requires `trade_params.exits.trailing_stop.activation_mode`, `trade_params.exits.trailing_stop.trail_mode`, and `trade_params.exits.trailing_stop.trail_value`.
- `trade_params.exits.trailing_stop.activation_mode=after_profit_pct` requires `trade_params.exits.trailing_stop.activation_profit_pct`.
- `trade_params.exits.trailing_stop.step_mode=step` requires `trade_params.exits.trailing_stop.step_value`.
- `trade_params.exits.time_stop.enabled=true` requires `trade_params.exits.time_stop.max_holding_minutes`.
- `trade_params.sizing.mode=target_notional` requires `trade_params.sizing.target_notional`.
- `trade_params.sizing.mode=risk_budget` requires `trade_params.sizing.target_risk_amount`.
- `trade_params.sizing.mode=fixed_quantity` requires `trade_params.sizing.target_quantity`.
- At least one of `trade_params.entry.price.acceptable_range` or `trade_params.execution_constraints.max_slippage_pct` should be present.
- `trade_params.position_management.allow_add_position=false` requires `trade_params.position_management.max_add_count=0`.

## AI Assembly Notes

- Use UTC ISO 8601 timestamps for `created_at` and `expires_at`.
- Keep `confidence` within `0..1`.
- Provide at least one non-empty `evidence` string.
- Do not include server-owned fields such as `signal_id` or `proposal_id`.

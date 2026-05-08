# AI Caller Guide

## Purpose

Use this guide only as a fallback after reading [submit-quickstart.md](submit-quickstart.md).
It should cover edge cases, conditional field traps, and exact enum reminders that the quickstart does not need to repeat.

## When To Open

- you need exact enum literals
- you are unsure which conditional field becomes required
- the schema error is unclear and you need a human-readable explanation
- the quickstart is not enough to resolve a sizing / trigger / exit combination

For complete field meaning and filling guidance, use `trade-plan-signal-parameter-design.md`.

Important:

- Real agent API responses may encode numeric values as strings.
- When reading trading context, treat numeric-looking strings such as `"10000"` or `"5"` as numeric field values rather than plain text labels.

## Allowed Enums

- `side`: `long | short`
- `position_hint`: `open | takeover | reverse | close`
- `position_intent`: `open | takeover | reverse | close`
- `trade_params.entry.trigger.type`: `immediate | touch_price | breakout | pullback_into_range`
- `trade_params.entry.price.order_type`: `market | limit`
- `trade_params.exits.stop_loss.mode`: `price | percent | none`
- `trade_params.exits.take_profit.mode`: `fixed_price | ladder | none`
- `trade_params.exits.trailing_stop.activation_mode`: `immediate | after_profit_pct | after_tp_hit`
- `trade_params.exits.trailing_stop.trail_mode`: `percent | price_delta`
- `trade_params.exits.trailing_stop.step_mode`: `continuous | step`
- `trade_params.sizing.mode`: `target_notional | risk_budget | fixed_quantity`
- `symbol_position.margin_type`: `cross | isolated`

## Conditional Field Rules

- If `position_intent` is `reverse`, set `replace_existing_position` to `true`.
- If `trade_params.entry.trigger.type` is `touch_price` or `breakout`, include `trigger_price`.
- If `trade_params.entry.trigger.type` is `pullback_into_range`, include `trigger_range.min` and `trigger_range.max`.
- If `trade_params.entry.price.order_type` is `limit`, include `limit_price`.
- If `trade_params.exits.stop_loss.mode` is `price`, include `stop_price`.
- If `trade_params.exits.stop_loss.mode` is `percent`, include `loss_pct`.
- If `trade_params.exits.take_profit.mode` is `fixed_price` or `ladder`, include at least one `targets` item.
- If `trade_params.exits.take_profit.mode` is `fixed_price`, include exactly one target and set `close_ratio` to `1`.
- If `trade_params.exits.take_profit.mode` is `ladder`, keep total `close_ratio` less than or equal to `1` and set `allow_partial_exit=true`.
- If `trade_params.exits.trailing_stop.enabled` is `true`, include `activation_mode`, `trail_mode`, and positive `trail_value`.
- If trailing activation is `after_profit_pct`, include positive `activation_profit_pct`.
- If trailing `step_mode` is `step`, include positive `step_value`.
- If `trade_params.exits.time_stop.enabled` is `true`, include `max_holding_minutes`.
- If `trade_params.sizing.mode` is `target_notional`, include `target_notional`.
- If `trade_params.sizing.mode` is `risk_budget`, include `target_risk_amount`.
- If `trade_params.sizing.mode` is `fixed_quantity`, include `target_quantity`.
- Include at least one of `trade_params.entry.price.acceptable_range` or `trade_params.execution_constraints.max_slippage_pct`.
- If `allow_add_position=false`, set `max_add_count=0`.
- If `trade_params.margin` is present, use only `mode=cross`; omit margin by default.

## Decision Edge Cases

- Use `position_intent=open` when there is no current symbol position and risk allows opening.
- Use `position_intent=takeover` when an existing same-side position should be actively replaced or re-owned by the new plan.
- Use `position_intent=reverse` only when an opposite-side position exists and reversal is explicitly intended.
- Use `position_intent=close` only when the strategy intent is to close an existing matching position.
- Reject or defer instead of forcing a payload when cooldown, exposure, or leverage rules block the trade.

## Directional Price Checks

- Entry reference price priority: `limit_price`, then `trigger_price`, then `acceptable_range` midpoint, then `trigger_range` midpoint.
- For `side=long`, price stop loss must be below entry reference price and take-profit targets must be above it.
- For `side=short`, price stop loss must be above entry reference price and take-profit targets must be below it.
- Ladder targets must ascend for long and descend for short.

## Validation Reminders

- Final structure should still be checked against `trade-plan-signal.schema.json`.
- If you need a concrete starting shape, open `payload-template.json`.
- If you need exact literal values, open `enums.md`.
- Before submitting, prefer `scripts/submit_trade_plan_signal.py`; it checks local payload traps and backfills `context_version` when possible.

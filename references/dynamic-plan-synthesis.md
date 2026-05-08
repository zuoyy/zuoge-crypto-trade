# Dynamic symbol-now plan synthesis for crypto-trader

## What changed

The crypto-trader opportunity planner in `/Users/zuo/.hermes/automation/crypto-trader-workflow/scripts/crypto_generate_plans.py` was refactored away from a setup-template-first approach into a state-driven plan synthesizer.

Current flow:

1. `evaluate_symbol_now()`
   - Reads current symbol/account state from live inputs.
   - Core fields include mark price, spread, funding, OI delta, book imbalance, volatility score, momentum bias, risk budget, account fit, and current position intent.

2. `evaluate_stage()`
   - Converts current state into a lightweight trading stage.
   - Current stages:
     - `sweep_reclaim`
     - `failed_breakout_reclaim`
     - `accepted_breakout`
     - `expansion_continuation`
     - `pullback_reaccept`
     - `trend_pressure_build`
     - `neutral_probe`

3. `decide_if_trade()`
   - Rejects symbols before plan synthesis when spread/funding/book/OI/risk budget/stage score do not justify a trade.
   - Typical explicit reject reasons now include:
     - `spread_too_wide`
     - `funding_too_hot`
     - `book_not_supporting`
     - `oi_contracting`
     - `stage_score_too_low`

4. `synthesize_trade_plan()`
   - Generates the actual one-off plan for the current moment.
   - This is symbol-specific and time-specific, not a static strategy template.

5. `map_stage_to_setup()`
   - Labels the synthesized plan with a setup name after stage evaluation.
   - Current mapping:
     - `sweep_reclaim` -> `liquidity_sweep`
     - `failed_breakout_reclaim` -> `false_breakout_recovery`
     - `accepted_breakout` -> `breakout`
     - `expansion_continuation` -> `volatility_expansion`
     - `pullback_reaccept` -> `pullback_confirmation`
     - `trend_pressure_build` -> `breakout_continuation`
     - fallback -> `trend_continuation`

## Important user preference learned

For this user, strategy planning should be understood as:

- one plan per symbol per current time point
- built from live market/account state
- setup label is secondary
- plan synthesis comes before naming the setup
- if the state is weak, output no opportunity plan

Do not frame the system as a library of static strategy templates.

## Contract discipline

Do not modify `zuoge-crypto-trade` contract fields when improving plan quality.
Keep improvements in the planning/synthesis layer unless the user explicitly asks to change the signal schema/skill contract.

## Current limitation

The stage model is still lightweight and feature-limited.
It does **not** yet use:

- explicit candle/K-line structure
- swing highs/lows
- reclaim levels
- multi-timeframe context
- event/news catalysts

So the current stage machine is useful, but it is still an approximation built from OI/funding/spread/book/volatility/momentum features.

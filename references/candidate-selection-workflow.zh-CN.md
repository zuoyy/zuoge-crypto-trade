# Candidate Selection Workflow for Crypto Trader

## Context

This note captures the workflow decision learned from a live build-out of the crypto-trader automation pipeline.

The user goal was not merely to query an account or manually submit a single signal. The real goal was:

- discover hot or promising Binance futures symbols
- combine them with account and position context
- generate complete trade plans
- push validated signals into the crypto-trader backend

## Key workflow lesson

Do **not** treat hot-token rankings as directly tradable signal sources.

Use this sequence:

1. Candidate discovery
   - trending
   - top search
   - social hype
   - smart money inflow
   - alpha / narrative lists
2. Binance contract tradability filter
   - must exist as Binance USDT-M perpetual
   - must be in trading state
   - reject thin / obviously non-executable symbols
3. Flow / volatility filter
   - prefer symbols with real money and expansion, not just social noise
4. Account-fit gate
   - current exposure
   - current position count
   - symbol cooldown
   - concentration / correlation concerns
5. Structure confirmation
   - clear invalidation
   - enough target space for asymmetric R multiple
6. Only then convert to TradePlanSignal payload and submit

## Directory decision

A user-level workflow preference emerged clearly:

- this crypto-trader pipeline should live in its **own standalone directory**
- do **not** mix it into the general `hermes-agent/workflow/` tree once the work grows beyond a quick experiment

Current isolated implementation location:

- `/Users/zuo/.hermes/automation/crypto-trader-workflow/`

## Current scaffold

The standalone pipeline currently includes:

- `scripts/run_crypto_pipeline.py`
- `scripts/crypto_collect_candidates.py`
- `scripts/crypto_filter_tradable.py`
- `scripts/crypto_generate_plans.py`
- `scripts/crypto_push_signals.py`

## Current limitation

The data plumbing and push path are working, but plan generation is still a scaffold.

Observed dry-run outcome:

- candidate collection worked
- tradable filtering worked
- account/trading-context reads worked
- push path worked in dry-run mode
- `plan_count` remained `0`

Meaning:
- the bottleneck is now structure detection / trade qualification, not transport
- future work should focus on setup recognition, OI/funding/depth filters, and account-intent routing

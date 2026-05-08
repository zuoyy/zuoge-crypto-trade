# Watchlist + Trigger-Plan Upgrade for Crypto Trader Workflow

## What changed

First priority optimization for `/Users/zuo/.hermes/automation/crypto-trader-workflow/`:

- Added layered output instead of binary `plan / rejected`
- Added `watchlist.json`
- Added `trigger-plans.json`
- Embedded `watchlist`, `trigger_plans`, and `rejection_stats` into `trade-plans.json`
- Downgraded several hard rejections into defer states instead of full discard

## New output model

The workflow should now separate candidates into four buckets:

1. `plans` — executable now
2. `watchlist` — structure still interesting, but not executable yet
3. `trigger_plans` — needs explicit confirmation before execution
4. `rejected` — low-quality or structurally invalid

## Rejection reasons that should be downgraded

These reasons were converted from hard reject into watch/defer states:

- `book_not_supporting` -> `watchlist`
- `directional_book_too_thin` -> `watchlist`
- `neutral_probe_too_weak` -> `trigger_plan`
- `inside_4h_range` -> `trigger_plan`
- `inside_1h_midrange` -> `trigger_plan`
- `neutral_probe_too_far_from_trigger` -> `trigger_plan`

Principle: do not throw away setups that are close but not ready.

## Verification result

Dry-run validation after the upgrade:

- run id: `20260506-opt2`
- collect: `110`
- filter: `12`
- executable plans: `0`
- watchlist: `5`
- trigger plans: `3`

This confirms the workflow moved from `0 output except rejects` to `deferred opportunity tracking`.

## Important pitfall discovered

The current `neutral_probe` thresholding is still too hard.
Observed trigger conditions like:

- `stage_score 提升到 >= 118.0`

This is a sign that `MIN_SETUP_SCORE`, `MIN_NEUTRAL_PROBE_SCORE`, and stage-score scaling are not well calibrated yet.

Implication:
- The watchlist/trigger-plan layer is now working.
- The next optimization pass should recalibrate `neutral_probe` so probe means *early reconnaissance*, not a near-complete setup.

## Practical guidance for future runs

When `plan_count == 0`, do not stop analysis at the rejection list.
Always inspect:
- `watchlist.json`
- `trigger-plans.json`
- `rejection_stats`

If those files exist and are populated, the workflow is behaving correctly as a structure-tracking engine even when no immediate order should be pushed.

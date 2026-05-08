# Crypto-trader workflow optimization notes (2026-05)

## User preference signal
- User prioritizes dynamic symbol-now plans with strict contract validity, concrete risk control, and structure-first execution.
- Prefer not forcing executable plans when market structure is immature; output watchlist / trigger-plan layers instead.
- Workflow should evolve toward dynamic rescanning and stateful promotion of near-ready setups.

## Implemented workflow upgrades
- Added watchlist/trigger-plan layered output to `crypto_generate_plans.py`.
- Added `watchlist.json` and `trigger-plans.json` run artifacts in `shared/crypto_workflow.py`.
- Downgraded several former hard rejects into watchlist/trigger-plan states:
  - `book_not_supporting`
  - `neutral_probe_too_weak`
  - `neutral_probe_book_too_weak`
  - `inside_4h_range`
  - `inside_1h_midrange`
  - `neutral_probe_too_far_from_trigger`
- Added richer watchlist schema:
  - `secondary_confirmation`
  - `invalidation_conditions`
  - `recheck_window_minutes`
  - `proximity_score`
  - `execution_readiness`
- Added `crypto_rescan_watchlist.py` to rescan prior watchlist/trigger-plan outputs and classify each symbol into:
  - `promoted`
  - `still_waiting`
  - `invalidated`
- Wired rescan into `run_crypto_pipeline.py` as a new `rescan` stage before push.

## Strategy-threshold adjustments
- `MIN_NEUTRAL_PROBE_SCORE` lowered from `118.0` to `62.0`.
- Added `MIN_TRIGGER_PLAN_SCORE = 54.0` to avoid promoting weak junk into trigger plans.
- `book_not_supporting` now distinguishes:
  - thin confirmation
  - short-term reversing book

## Current limitation discovered
- Rescanner writes `rescan-summary.json` but does not yet rewrite standard downstream artifacts such as promoted executable plans for push consumption.
- Next likely upgrade: push stage should prefer rescanned promoted plans, and rescanner should emit normalized promoted/remaining/invalidated files.

## Verification pattern
- Compile:
  - `python -m py_compile scripts/crypto_generate_plans.py scripts/crypto_rescan_watchlist.py scripts/run_crypto_pipeline.py`
- Dry-run full pipeline:
  - `python scripts/run_crypto_pipeline.py --run-id <id> --dry-run`
- Dry-run rescanner against previous run:
  - `python scripts/crypto_rescan_watchlist.py --run-id <new_id> --source-run-id <old_id>`
- Inspect:
  - `state/runs/<id>/trade-plans.json`
  - `state/runs/<id>/watchlist.json`
  - `state/runs/<id>/trigger-plans.json`
  - `state/runs/<id>/rescan-summary.json`

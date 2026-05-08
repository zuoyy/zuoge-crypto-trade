# Watchlist rescanner upgrade (2026-05)

## What was added
- New script: `scripts/crypto_rescan_watchlist.py`
- New workflow stage in `scripts/run_crypto_pipeline.py`: `rescan`
- Pipeline now runs `collect -> filter -> plan -> rescan -> push`
- Rescan mutates the current run's `trade-plans.json`, `watchlist.json`, and `trigger-plans.json`
- New output artifact: `state/runs/<run_id>/rescan-summary.json`

## Purpose
When the workflow produces no executable plans but does produce watchlist / trigger-plan candidates, do not wait for a human to manually re-read them.
Run a second pass that:
1. Loads prior `filtered.json`
2. Loads prior `watchlist.json` and `trigger-plans.json`
3. Refreshes trading context and exchange metrics
4. Re-runs `build_plan()` for each symbol
5. Classifies each symbol as:
   - `promoted`
   - `still_waiting`
   - `invalidated`

## Implementation notes
- Current implementation reads artifacts from `--source-run-id`.
- It writes a single `rescan-summary.json` with:
  - `promoted_plans`
  - `invalidated`
  - `rescanned`
  - count fields
- This validates dynamic reassessment without yet mutating the canonical push inputs.

## Current limitation
- Rescanner is no longer summary-only. It now rewrites the current run's downstream artifacts so push consumes rescanned truth.
- Current scope: it auto-loads the latest previous run with pending `watchlist` / `trigger_plans`, rescans up to a bounded number of symbols, and merges them into the current run.
- Pending lifecycle is now tracked on each carry-over setup:
  - `age`
  - `retry_count`
  - `ttl`
  - `previous_status`
  - `state_transition_reason`
- Expiry rules now invalidate stale setups on rescan when retry limit or TTL is exceeded.
- Next upgrade should add stronger promotion rules plus optional symbol-specific TTL tuning.

## Verification
- Compile:
  - `python -m py_compile scripts/crypto_rescan_watchlist.py scripts/run_crypto_pipeline.py scripts/crypto_generate_plans.py`
- Run against a prior watchlist-producing run:
  - `python scripts/crypto_rescan_watchlist.py --run-id <new_id> --source-run-id <old_id>`
- Inspect:
  - `state/runs/<new_id>/rescan-summary.json`
- Expected healthy outcome can be:
  - `promoted_count = 0`
  - `invalidated_count = 0`
  - `unresolved_count > 0`
  This means the market still has no clean executable structure, but the rescanner is functioning.

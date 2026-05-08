# Rescan-to-push state handoff (2026-05)

## What changed
- `crypto_rescan_watchlist.py` now writes normalized rescan state, not just a summary:
  - `promoted_plans`
  - `remaining_watchlist`
  - `remaining_trigger_plans`
  - `invalidated`
- It also writes current-run downstream artifacts:
  - `watchlist.json`
  - `trigger-plans.json`
- `crypto_push_signals.py` now:
  - reads `rescan-summary.json` if present
  - prefers rescanned `promoted_plans`
  - falls back to `source_run_id`'s `trade-plans.json` when the rescan run has no local `trade-plans.json`

## Why this mattered
Earlier rescanner behavior only proved reclassification logic.
It did **not** complete the state transition into downstream push inputs.
That created two failure modes:
1. push could ignore rescanned truth and still read stale pre-rescan `plans`
2. push could crash on a pure rescan run because `trade-plans.json` was missing locally

## Verified pattern
Commands used:
- `python3 -m py_compile scripts/crypto_rescan_watchlist.py scripts/crypto_push_signals.py`
- `python3 scripts/crypto_rescan_watchlist.py --run-id <rescan_run> --source-run-id <source_run>`
- `python3 scripts/crypto_push_signals.py --run-id <rescan_run> --dry-run --limit 5 --management-limit 5`

Healthy outcomes:
- rescanner may return:
  - `promoted_count = 0`
  - `invalidated_count >= 0`
  - `remaining_count > 0`
- push should still succeed on the rescan run
- `signals.json` should be generated even when no promoted plans exist

## Important nuance
- `remaining_count` is an entry count, not necessarily a distinct symbol count.
- A symbol may appear in both `remaining_watchlist` and `remaining_trigger_plans`.
- If backlog monitoring needs true symbol exposure, add a separate `remaining_symbol_count` metric.

## Next likely refinement
If output semantics matter for observability, make `signals.json.opportunity_source` three-state instead of binary:
- `rescan-promoted`
- `rescan-promoted-empty`
- `plans`

That separates:
- no opportunity after rescan
from
- no rescan path involved at all.

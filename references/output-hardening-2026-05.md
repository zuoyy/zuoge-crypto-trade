# Crypto Trader Workflow Output Hardening — 2026-05

## What changed

This session hardened the standalone workflow at `/Users/zuo/.hermes/automation/crypto-trader-workflow/` from a binary `plan/reject` system into a layered output system:

- added `watchlist.json`
- added `trigger-plans.json`
- embedded `watchlist`, `trigger_plans`, and `rejection_stats` into `trade-plans.json`
- reclassified some hard rejects into:
  - `watchlist`
  - `trigger_plan`

## Concrete implementation notes

### New artifacts
Shared path helper now exposes:
- `watchlist`
- `trigger_plans`

These are persisted alongside:
- `candidates.json`
- `filtered.json`
- `trade-plans.json`
- `signals.json`
- `telegram-cards.txt`

### Decision downgrades added
In `crypto_generate_plans.py`, `classify_trade_decision()` now converts selected reject reasons into softer outputs.

Current downgrade behavior:
- `book_not_supporting`
- `directional_book_too_thin`
  - downgraded to `watchlist`
  - split into:
    - thin confirmation
    - reversing book
- `neutral_probe_too_weak`
- `stage_score_too_low` when `stage_name == neutral_probe`
  - downgraded to `trigger_plan` only when score/distance still justify monitoring
- `inside_4h_range`
- `inside_1h_midrange`
- `neutral_probe_too_far_from_trigger`
  - downgraded to `trigger_plan`

### Threshold changes
Important scoring change:
- `MIN_NEUTRAL_PROBE_SCORE` was reduced from `118.0` to `62.0`
- added `MIN_TRIGGER_PLAN_SCORE = 54.0`

Reason: `neutral_probe` should behave like an early reconnaissance layer, not an executable-plan threshold masquerading as a probe.

### New watchlist / trigger fields
Watchlist items and trigger plans now include:
- `secondary_confirmation`
- `invalidation_conditions`
- `recheck_window_minutes`

This makes outputs suitable for future rescanning / alerting passes instead of being one-shot human notes.

## Validation snapshots
Dry-run verification during the session:

- `20260506-opt1`: `plan_count=0`, `watchlist_count=6`, `trigger_plan_count=3`
- `20260506-opt3`: `plan_count=0`, `watchlist_count=5`, `trigger_plan_count=2`
- `20260506-opt4`: `plan_count=0`, `watchlist_count=3`, `trigger_plan_count=1`

The key improvement was not more forced executable plans; it was converting near-miss structures into structured monitorable outputs.

## Remaining gaps
Future agents should consider the following next:

1. `neutral_probe_book_too_weak` still often behaves like a watchlist candidate and may deserve downgrade logic instead of hard rejection.
2. `spread_too_wide` is still a hard reject; for transient spread dislocations, a low-priority watchlist may be more useful.
3. If many consecutive runs still produce zero executable plans, inspect whether RR gating, stop/target synthesis, or trigger anchoring is too conservative rather than simply relaxing structural gates.

## Files touched this session
- `shared/crypto_workflow.py`
- `scripts/crypto_generate_plans.py`

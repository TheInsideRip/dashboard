# ADR-059 — ML/RL First Capture (2026-06-24)

**Status:** documentation-only companion to ADR-059. **Authorizes nothing.** ADR-059 remains **DRAFT / Proposed**.
**Date:** 2026-06-24
**Scope:** records the outcome of the single authorized capture-only run. No code/DB/table change is made by this file.

---

## Command run

```
python 08_odds_and_edges.py --mlrl-capture-only --save
```

## Result (verified read-only after the run)

- mlrl_full_slate total rows = 52
- rows inserted for 2026-06-24 = 52
- distinct games = 13
- markets = ML 26 / RL 26
- sides = away 26 / home 26
- complete 13 × 4 grid (ML/away 13, ML/home 13, RL/away 13, RL/home 13)
- price_source_policy = primary:fanduel on all 52 rows
- price_missing = 0
- FanDuel-priced rows = 52
- fallback_flag = 8
- mlrl_tracker stayed unchanged at 1,247

## Scope

- capture-only run succeeded
- selected-pick logging skipped (mlrl_tracker untouched at 1,247)
- actionable edge report suppressed
- K props and totals did not run
- no edge tests
- no picks
- no 09g --apply
- no .bat wiring
- ADR-059 remains DRAFT

Retained, as authorized: `_save_odds_lookup` wrote 15 rows to `game_odds_lookup`
(raw ML-price cache, not a selected-pick log) — explicitly part of expected
capture-only behavior, not a new write target.

## Notes

- 13 games were captured instead of 16 because capture only uses **matched upcoming
  pregame odds**. Already-started events (the run reported "Skipped 2 events already
  in progress") and games without a matchable upcoming odds event are excluded by design.
- 24 intra-run duplicate rows were skipped by the write-once `UNIQUE(game_pk, market, side)`
  key due to duplicate odds-event matching (the run reported "Matched 19/16"). The table
  was empty before this run, so these are intra-run duplicates — **not** a re-run. This is
  expected and confirms **first-write-wins** behavior.
- Odds API usage for the run: 4 quota requests.

## What this file does NOT do

No DB write, no table change, no production-code change, no edge test, no picks,
no resolver apply, no .bat wiring, no ADR-059 promotion.

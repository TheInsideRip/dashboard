# ADR-043: substrate v2 not wired — live contamination confirmed

Status: Accepted
Date: 2026-06-07
Session: 44
Extends: ADR-028 (06a outer-loop bug), ADR-033 (03c starter row-order bug)
         — does NOT supersede either; this is a status confirmation + reinforced hold.

## Context

ADR-028 and ADR-033 each diagnosed a builder bug that poisons the K-prop /
pitcher-outs substrate, and each built a corrected `*_v2` table side-by-side:

- ADR-028: `06a_cumulative_pitcher_metrics.py` has a relief-drop outer-loop bug
  (it iterates only over a pitcher's *start* games, so relief appearances never
  enter the cumulative counters). Corrected builder: `06a_v2_*` →
  `pitcher_cumulative_v2`.
- ADR-033: `03c_team_aggregations.py` picks the starter with `.agg("first")` over
  a `SELECT ... FROM pitches_historical` that has no `ORDER BY`, so the "starter"
  is whichever row SQLite stored first (empirically reverse-chronological → a
  late-inning reliever). The starter's ~85 pitches get counted as bullpen pitches,
  inflating `bp_pitches_today` / `bp_pitches_prior_3d`. Corrected builder:
  `03c_team_aggregations_v2.py` → `bullpen_workload_v2` / `bullpen_stats_v2`.

Both ADRs framed the corrected tables as Phase-2 deliverables awaiting Phase-3
re-validation and Phase-4 cutover. This ADR records a first-hand verification of
the **current wiring state** of the live repo on 2026-06-07.

### Finding — v2 was never cut over; serving reads v1

The daily pipeline rebuilds the v1 tables with the buggy builders and the entire
serving path reads v1, not v2 (verified by grep over the live tree):

| Script | Line | Reads |
|--------|------|-------|
| `07_predict_today.py`     | 89  | `pitcher_cumulative` |
| `11_predict_totals.py`    | 206 | `pitcher_cumulative` |
| `11b_predict_mlrl.py`     | 347 | `pitcher_cumulative` |
| `27i_k_prop_tagger.py`    | 159 | `pitcher_cumulative` |
| `22l_tag_validated_edges.py` | 278 | `pitcher_cumulative` (`cum_games`) |
| `28i_outs_pipeline.py`    | 360 | `bullpen_workload` (`WHERE game_date = ?`) |

No serving script reads either `pitcher_cumulative_v2` or `bullpen_workload_v2`.
The only v2 readers are analysis/diagnostic scripts (`10a_v2_substrate_for_phase3.py`,
the `diag_adr033_*` family). The builders confirm the write targets:
`06a_cumulative_pitcher_metrics.py:565` writes `pitcher_cumulative`
(`if_exists='replace'`); `03c_team_aggregations.py:493` writes `bullpen_workload`
(`if_exists="replace"`).

### Finding — the contamination reaches LIVE consumed data, not just backtest

`05c_pregame_context.py` reads the bullpen-workload fields from `bullpen_workload`
(v1) at lines 525–535 and writes them into `game_context`
(`to_sql('game_context', ... 'append')` at :735), as
`home_/away_bp_pitches_prior_3d`. `game_context` is exactly what the live outs
tagger `28i_outs_pipeline.py` consumes. So the 03c inflation flows straight into
the production tagger.

DB check (live `mlb_model.db`, 2026-06-07): on the latest slate present in
`game_context`, `bullpen_workload` (v1) and `bullpen_workload_v2` simultaneously
(2026-05-22), **28 of 30 team-sides have `game_context` == v1 and ≠ v2**; the
other 2 had no v1 row either (still not sourced from v2). The contamination is
**~2–2.5x multiplicative** (e.g. HOU 233 v1/gc vs 84 v2; NYY 383 vs 155; CLE 398
vs 167). Because the P20 freshness cutoff that OUTS_UNDER keys off is inflated in
parallel, relative ranking is **partly** preserved — but the absolute metric is
wrong and the qualifying universe shifts.

> NOTE on staleness: `bullpen_workload_v2` was last built **2026-05-22**, so today's
> slate (2026-06-07) has no v2 rows at all. v2 is not merely un-wired; it is not
> being maintained. This strengthens, not weakens, the finding.

### Selection impact

Under v2, approximately **1 in 9 team-dates** flip their fresh / not-fresh
qualification. *(Measured on the Cowork copy; re-run on live before treating as
final — the live re-run was NOT performed in this session.)* Written as a ratio
deliberately: a bare "11.4%" would be conflated with the unrelated ML_BP_EXHAUST
"+11.4% ROI" figure already in the docs.

## Decision

1. **Outs hold reaffirmed and strengthened.** OUTS_UNDER_STRONG / OUTS_UNDER_ELITE
   remain on hold (Session 32 D4, ADR-033). This ADR deepens the rationale: the
   contamination is now confirmed in the LIVE tagger input (`game_context`), not
   only in historical backtest. The hold is not relaxed.
2. **v2 cutover is REQUIRED but GATED** on ADR-028 / ADR-033 Phase 3
   re-validation. It is NOT executed here.
3. **No serving-path code edits this session.** This is a documentation +
   operational-status deliverable only.

## Alternatives considered and rejected

**(a) Cut `bullpen_workload` / `pitcher_cumulative` over to v2 now.**
Rejected — same reason as ADR-028(a)/ADR-033(a): cutover before Phase 3
re-validation invalidates every BP-dependent edge overnight with no replacement
validated numbers. Phase 3 must run first.

**(b) Treat this as already covered by ADR-028/033 and write nothing.**
Rejected. ADR-028/033 documented the *bugs* and built v2; neither recorded the
first-hand confirmation that v2 is still un-wired AND unmaintained, nor that the
contamination is present in live `game_context` (not just backtest substrate).
That live-reach is the new, decision-relevant fact.

**(c) Lift the outs hold because relative ranking is partly preserved.**
Rejected. "Partly preserved ranking" is not "validated edge." The qualifying
universe shifts (~1 in 9 flips) and the metric name does not match its meaning;
publishing on it repeats the ADR-033 interpretability error.

## Consequences

- The K and pitcher-outs edges currently sit on a **confirmed-contaminated live
  substrate**. Their inherited WR/ROI numbers are v1-substrate figures pending a
  v2 re-run; they should be read with that caveat everywhere they appear.
- The totals predictor is **market-quality and is NOT the problem**: model
  corr(predicted_total, actual_total) = **0.182** on `game_totals_backtest`
  (n=7,283), versus a book corr of ~0.19–0.20 (book_line vs result_total,
  totals_tracker n=564) — verified against the live DB this session. The substrate
  bug is a selection/threshold problem on BP-keyed edges, not a totals-model
  accuracy problem.
- Pre-cutover and post-cutover tracked bets will be different populations
  (same caveat pattern as ADR-024 / ADR-028 / ADR-031 / ADR-033).

## Out of scope (named so they are not silently pulled in)

Each is a separate future ADR / deliverable:

- v2 edge win-rate re-runs (OUTS_UNDER family, ML_BP_EXHAUST family,
  model-mediated UNDER_*/HIGH_PARK_GAP) — NOT done here.
- sigma / probability calibration of the totals model.
- train/serve substrate unification (10a_v3 reading v2 + cutover).

## References

- ADR-028 — 06a outer-loop (relief-drop) bug; multi-phase substrate-rebuild precedent.
- ADR-033 — 03c starter row-order bug; `bullpen_workload` inflation root cause,
  Phase 1 (99.4% mismatch) + Phase 2 (v2 build) status.
- ADR-031 — 05c BP staleness fallback (fixed staleness, not the underlying metric).
- ADR-032 — season hardcode bug (same no-backfill / forward-reset decision pattern).
- `RULES_FOR_CLAUDE.py` S4 (stale thresholds) and S6 (silent-fallback / aggregate
  misread) — same families.

## Process note (Session 44)

The seven load-bearing claims behind this ADR were reproduced first-hand against
the live repo before anything was written (the Cowork findings were treated as a
hypothesis, not fact). The one claim that did not reproduce as literally stated —
"today's `game_context` differs from v2" — failed only because v2 has no rows for
today; tested on the latest overlapping slate it confirmed cleanly. Discrepancy
surfaced, not papered over.

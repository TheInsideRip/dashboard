# ADR-050 (Accepted): R3 K-prediction reconstruction — substrate/formula VALIDATE, but the V1/V2 gate FAILS on a second plumbing gap (game_context lineup composites are not point-in-time)

> **PLUMBING GAP CLOSED 2026-06-13:** the mutating lineup input (`lineup_k_pct`) is now snapshotted at serve time — `08::save_full_slate_k` stores it (and `has_lineup`) directly from the `predict_pitcher` return dict into `k_prop_full_slate`, so it is no longer reconstructed from a mutated `game_context`. Forward V1/V2 gate verified 100% (16/16 same-run, 2026-06-13). Backward R3 reconstruction stays blocked (historical lineups remain non-point-in-time); fit re-runs on clean forward data only.

Status: **Accepted** (promoted from DRAFT 2026-06-13) — read-only reconstruction per
`claude_code_prompt_kprop_r3_reconstruction.md`. Outcome: **V1/V2 HARD GATE FAILED →
fit FORBIDDEN → calibration question remains INDETERMINATE.** Confirms ADR-048/049;
does not reopen them. Only write = research table `k_prop_r3_reconstructed`.
Relates to: ADR-049 (predictions not stored), ADR-032 (season-hardcode), ADR-045/047.

> All claims verified first-hand, read-only, 2026-06-12.

## What was attempted
Reconstruct R3 (2026-05-17→06-06) full-slate K predictions point-in-time to unblock the
ADR-049 fit: v1 `pitcher_cumulative` (C1, R3 read v1 — verified by diff), today's 07
`predict_pitcher` imported verbatim (C3 — formula byte-identical to R3-era except the table
name), point-in-time row `game_date < start_date` (C2), actuals from `pitches_historical`
per (pitcher, game_pk) (C4). 564 R3 starts reconstructed; 292 joinable to `bet_tracker`.

## V1/V2 HARD GATE — FAILED (verified)
| basis | match `|Δ|≤0.05` vs served `bet_tracker.predicted_k` |
|---|---|
| with current `game_context` lineup | 247/292 = **84.6%** |
| forcing NO lineup adjustment | 208/292 = 71.2% |
| **PASS bar** | **≥99% — NOT met → HALT** |

## Root cause — isolated and diagnostic (verified)
- **The substrate + formula reconstruction is PROVABLY CORRECT:** on the
  cumulative-source, **no-confirmed-lineup** subset = **136/136 (100.0%)** exact match.
  C1/C2/C3 are right.
- **The failure is entirely the lineup adjustment:** **43 of 45 mismatches are on
  `lineups_confirmed=1` games** (the other 2 are `pitcher_stats`-fallback look-ahead).
- Neither the **current** stored `game_context.lineup_k_pct` (84.6%) nor **no** lineup
  (71.2%) reproduces what 07 served → the lineup composite 07 used at serve time has been
  **overwritten/recomputed**. `game_context` lineup fields are **NOT point-in-time-stable**.

## The finding (Rule-12 surface): a SECOND plumbing gap, distinct from ADR-049
ADR-049: the *predictions* were never stored. ADR-050: even the *inputs* aren't
point-in-time-snapshotted — `game_context.{side}_lineup_k_pct` is mutated after serving, so
any historical prediction that consumed a confirmed-lineup adjustment (~57% of R3 games:
161/285 confirmed) **cannot be faithfully reconstructed.** Reconstruction works only for the
~43% of games 07 served without a confirmed-lineup adjustment.

## Decision
**Do NOT fit.** The full-slate clean R3 set the calibration needs cannot be assembled
faithfully (the lineup-confirmed majority is unrecoverable). Per the hard gate, fitting on a
reconstruction that fails validation is forbidden. Calibration fittability stays
**INDETERMINATE** — which confirms ADR-048. (Restricting the fit to non-lineup-confirmed games
is possible — that subset validates 100% — but it is a selection on lineup-confirmation status
that may bias the calibration and shrinks N; not done here, flagged as a decision for PJK.)

## What's needed (build task, not done here — reinforces ADR-049's recommendation)
Persist, write-once at pregame: full per-start K predictions **AND a snapshot of every input
that feeds them** (the lineup composite used, the cumulative row id, source flag). Without an
input snapshot, even a deterministic model cannot be reconstructed once `game_context` mutates.
Then the calibration question becomes answerable on forward data. Until then it is blocked by
absence of point-in-time data, not by evidence of a flat curve.

## Artifact
`k_prop_r3_reconstructed` (research-marked, 564 rows): pitcher, game_pk, game_date, side,
reconstructed predicted_k, source, actual_k, tbf, pa, was_bet, bet_tracker_predicted_k.
**Caveat: rows on `lineups_confirmed=1` games are NOT faithfully reconstructed (recon≠served)
— validated only for the cumulative-source, non-confirmed-lineup subset. Do not fit the full
table.** No serving/tracker/predictor code touched.

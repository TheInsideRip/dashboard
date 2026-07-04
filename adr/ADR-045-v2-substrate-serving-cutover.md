# ADR-045: v2 substrate serving cutover (betting path)

Status: Accepted
Date: 2026-06-07
Session: 45
Relates to: ADR-043 (v2 not wired / live contamination — cutover GATED on Phase-3
            re-validation), ADR-044 (OUTS_UNDER demotion on v2). This ADR executes
            the cutover that ADR-043 gated, on the evidence ADR-044 + the totals
            re-validation produced.

> All figures below were verified first-hand against the live repo / DB on
> 2026-06-07, not asserted from a handoff.

## Context

ADR-028 (06a relief-drop) and ADR-033 (03c starter row-order) built corrected
`*_v2` substrate tables side-by-side; ADR-043 confirmed the daily pipeline and the
full serving path still read the contaminated v1 tables, and gated cutover on
Phase-3 re-validation. This session rebuilt the stale v2 tables, re-validated the
edges on the corrected substrate, and — on the evidence below — cut the **betting**
serving path over to v2.

### Substrate rebuild (verified)
- `pitcher_cumulative_v2`: **15,506 rows**, max `game_date` 2026-06-06 (== v1 max),
  built by `06a_v2_cumulative_pitcher_metrics.py`. The relief-drop fix added
  **+352** newly-qualifying starts vs v1 (15,154); 0 shared-key rows have v2
  `cum_pitches` < v1 (fix only adds relief pitches). Spot-checks: deGrom
  (pure starter) v1==v2 `cum_xwoba_allowed`=0.2821; Brazoban (relief usage)
  v1 0.2402 → v2 0.2914 — confirming rate features were contaminated for
  relief-using pitchers only.
- `bullpen_workload_v2`: **16,201 rows** (now 16,231 incl. today's bridge), built
  by `03c_team_aggregations_v2.py` (4 invariants PASS). ~2x deflation vs v1;
  `bp_pitches_prior_3d` P20 253→110, P75/P90 196/234.
- `bullpen_stats_v2`: 120 rows. `game_totals_backtest_v2` rebuilt on **full v2**
  (`pitcher_cumulative_v2` + `bullpen_stats_v2`, via `10a_v2_substrate_for_phase3.py`
  patched to read `bullpen_stats_v2`): **8,267 rows**.

### Evidence the cutover is correct
- **Outcome reconstruction** (needed to validate outs): the original event-counting
  method ceilinged at ~78% vs 2026 booked `outs_tracker`; the innings-based
  out-state-progression method validated at **99.6%** (prototype) / **98.5%**
  (in-backtest). The outs pre-reg (`PHASE_3_OUTS_PREREG_001.py`) was amended +
  re-locked to v2.0 (gate-forced; no aggregate computed under v1.1).
- **Totals edges SURVIVE on full v2** (joined to `historical_odds` median totals
  line, G0 line-sanity PASS, median 8.5): HIGH_PARK_GAP **69.7% WR, n=76,
  RE-VALIDATED 3/3**; UNDER_GAP **55.2% WR, n=1,558, RE-VALIDATED 3/3**. The totals
  model's correlation was unchanged across the rebuild (0.182 → 0.183).
- **OUTS_UNDER DEMOTES on v2** (ADR-044): STRONG ≥17.5 → 52.1% (1/3), ELITE ≥18.5 →
  56.3% (1/3). Acceptable because outs are not bet.

## Decision

Cut the **betting** serving path from v1 to v2 and bridge the daily v2 today-row;
leave the outs pipeline on v1.

### Serving reads cut to v2 — VERIFIED on disk 2026-06-07
| file | substrate read(s) now |
|------|------------------------|
| `05c_pregame_context.py` | `bullpen_workload_v2` (L527), `bullpen_stats_v2` (L540) |
| `07_predict_today.py` | `pitcher_cumulative_v2` (L89) |
| `11_predict_totals.py` | `pitcher_cumulative_v2` (L206), `bullpen_stats_v2` (L300) |
| `11b_predict_mlrl.py` | `pitcher_cumulative_v2` (L347), `bullpen_stats_v2` (L407) |
| `27i_k_prop_tagger.py` | `pitcher_cumulative_v2` (L159) |
| `22l_tag_validated_edges.py` | `pitcher_cumulative_v2` (L278, `cum_games` gate) |

This session edited 22l, 07, 11b (one-line table-name swaps each; backed up to
`*.bak_v2cut_20260607_*`; diffs confirmed table-name-only; all compile). 05c, 11,
27i were already on v2 from earlier in the session.

### Daily bridge — VERIFIED
`populate_today_bp_workload.py` now **dual-writes** both `bullpen_workload` (v1) and
`bullpen_workload_v2` in one transaction. The `--apply` this session wrote today's
30 v2 rows (range 71–324, P75/P90 196/234) and left the 30 v1 rows byte-identical to
the pre-apply backup; `bullpen_workload_v2` max date is now **2026-06-07** — the
one-day v2 lag is closed. v1 remains written so it stays a live audit baseline.

### Intentionally left on v1
- **`28i_outs_pipeline.py`** still reads `bullpen_workload` (v1, L360). Left v1 on
  purpose: outs demoted on v2 (ADR-044) and not bet; its primary BP input is
  `game_context` (now v2 via 05c on the next clean run); editing it adds risk for
  no betting benefit. **Known remaining v1 reader.**
- **`29a_mlrl_bp_tagger.py`**: disabled in `pregame_pipeline.bat` (BP threshold
  stale); no substrate read; out of scope.

## Consequences

- The K-prop, totals, and MLRL betting paths now read a consistent, corrected v2
  substrate. The split-substrate hazard flagged mid-session (07 v1 / 27i v2;
  11 v2 / 22l v1) is resolved.
- **No 05c re-run today.** Tonight's games already started; re-pulling would corrupt
  the existing `game_context`. The v2 BP feed into `game_context` takes effect on the
  **next clean pregame run** (tomorrow). Until then today's `game_context` BP fields
  remain v1-derived from this morning's run.
- **Residual v1 reads:** 28i (above). `game_context` rows written before tomorrow's
  run carry v1-scale BP; trailing-window/P20 consumers see a mixed scale until the
  window flushes (same transition caveat as ADR-031/033).
- Behavior changes: 07 and 11b K/contact features now differ for relief-using
  pitchers (e.g. Brazoban xwOBA 0.2402→0.2914); 22l's `cum_games` gate is
  unchanged (start-count identical v1/v2 — consistency edit only).
- **Line-basis caveat (ADR-035):** the totals RE-VALIDATED verdicts are vs the
  retail/median line, not the closing/sharp line; edge magnitude may compress
  against close. Re-running HIGH_PARK_GAP vs a sharp/closing line is a separate task.

## Rollback

- Serving files: restore `22l/07/11b_*.bak_v2cut_20260607_*` over the originals
  (05c/11/27i edits predate this session).
- Substrate today-rows: `bullpen_workload(_v2)_bak_precutover_20260607_164121`.
- `populate_today_bp_workload.py.bak_dualwrite_20260607_163358`,
  `10a_v2_substrate_for_phase3.py.bak_v2patch_20260607_161032`.

## Notes / cleanup

- Code comments in 05c / populate / the bullpen patch say "ADR-044 cutover"; per
  this session ADR-044 is the **outs demotion** and this cutover is **ADR-045**.
  The in-code "ADR-044" references should be corrected to ADR-045 (doc-only, not
  done here to avoid touching serving files beyond the table-name swaps).
- ADR-044 (outs demotion) is a separate pending deliverable.

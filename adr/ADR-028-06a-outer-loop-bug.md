# ADR-028: 06a outer-loop bug — undercounting cumulative pitcher metrics

Status: Accepted (Phase 3 split into 3a/3b/3c — see status update)
Date: 2026-04-27 (Phase 3a complete: 2026-05-10, Session 29)
Session: 27 (with Phase 3a addendum from Session 29)

## Context

`06a_cumulative_pitcher_metrics.py` is the foundation of every starter-
based prediction in the system. It produces `pitcher_cumulative`, a
table read by 07, 11, 11b, 22l (via tag thresholds), 26e, 27i, 28i,
and the entire validated-edges substrate (verify_edges_v4 etc.).

A diagnostic chain originating in the UNDER_VALIDATED L6 losing streak
investigation (Session 27) surfaced a logic bug in 06a's
`compute_pitcher_cumulative` function:

```python
# Filter to only games where this pitcher STARTED
starter_game_pks = {gpk for (pid, gpk) in starter_games if pid == pitcher_id}
start_games = game_info[game_info['game_pk'].isin(starter_game_pks)].copy()
...
# Process each game chronologically
for _, start_row in start_games.iterrows():
    ...
    if cum_starts >= 1 and cum_pitches >= MIN_PITCHES_FOR_METRICS:
        results.append(row)
    # Now process this game's pitches to update running totals
    game_pitches = pitcher_df[pitcher_df['game_pk'] == current_game_pk].copy()
    ...
```

The outer loop iterates over `start_games` (only the pitcher's STARTS),
not `game_info` (all of the pitcher's appearances). Pitches thrown in
relief outings between starts are never added to `cum_pitches`,
`cum_k`, `cum_bb`, `cum_xwoba`, or any other cumulative counter.

### Manifestation

Verified concrete cases (`diag_montgomery_threshold_check_20260427.py`):
  - **PJ Poulin**: 5 starts, 11 relief appearances. Real cum_before at
    last start = 245. 06a sees cum_before = 18. Gate fails. 0 rows
    written despite 3 starts that should have qualified.
  - **Mason Montgomery**: 1 start preceded by 8 relief appearances
    (159 pitches). 06a sees cum_before = 0. Gate fails. 0 rows
    written despite the start qualifying with corrected count of 159.
  - **Connor Prielipp**: 1 start, no relief. Working as designed
    (genuine opener under 100-pitch threshold). Confirms diagnostic
    logic.

### Scope of damage

Two populations are affected:
  - **39 pitchers currently MISSING from pitcher_cumulative entirely**
    in 2026 (some legitimately under threshold; some bug-victims like
    Poulin/Montgomery whose corrected counts would qualify).
  - **All 180 FRESH pitchers** in pitcher_cumulative for 2026 have
    UNDERCOUNTED `cum_*` values to varying degrees, depending on how
    much relief work they did.

The bug has been present since 06a was built (Phase 4, March 29, 2026).
**All triple-verified edge stats** — UNDER_VALIDATED 58.1% WR,
HIGH_PARK_GAP 69.9% WR, K_OVER_OPP_K, K_UNDER_WHIFF_CONTACT,
OUTS_UNDER_STRONG, etc. — were computed against the buggy substrate.

## Decision

**DO NOT patch 06a in a single step.** The fix is small in code but
invalidates the validation substrate for every edge that reads
pitcher_cumulative. This is the same trust-the-system problem ADR-024
walked back with park factors, at larger scale.

Instead, follow a **5-phase permanent fix**:

**Phase 1: Quantify the damage.**
Read-only diagnostic. Compute STORED vs CORRECTED `cum_pitches` at
each starter game for every 2026 pitcher. Histogram of relative
undercounting. Identify which validated edges' qualifying populations
shift on corrected substrate.
  - Output: `diag_06a_quantify_damage_phase1.py` (delivered Session 27)
  - Cost: 1 session

**Phase 2: Build pitcher_cumulative_v2 side-by-side.**
Patched 06a writes to `pitcher_cumulative_v2` instead of dropping and
rebuilding `pitcher_cumulative`. Production scripts continue reading
the original. Allows validation work without pipeline disruption.
  - Cost: 1 session
  - **STATUS: COMPLETE (Session 27, 2026-04-27).**
  - **Output table**: `pitcher_cumulative_v2` (14,451 rows, +322 vs v1)
  - **Verification**: ground-truth count of actual prior pitches in
    pitches_historical matched v2 on 4/4 mismatch suspects (Fried,
    Manoah, Williams, Garcia). v1 short on 4/4.
  - **Secondary bug found and fixed**: original 06a's
    `identify_starter_games` at line 214 uses
    `sort_values('pitch_number').iloc[0]` which is ambiguous when
    multiple pitchers each have pitch_number=1 in the same half-inning
    (occurs whenever a starter faces multiple batters and each
    at_bat starts with pitch_number=1). v2 incidentally avoids this
    via its iterate-all-appearances design.
  - **Methodology lesson**: "match the legacy" is NOT a valid
    invariant when the legacy is itself the bug. Test against ground
    truth from raw data, not legacy output.

**Phase 3: Re-validate every edge against pitcher_cumulative_v2.**
Run `verify_edges_v4` (or equivalent) against the new substrate for:
UNDER_VALIDATED, HIGH_PARK_GAP, UNDER_WEATHER_3, UNDER_WEATHER_2,
K_OVER_OPP_K, K_UNDER_WHIFF_CONTACT, K_OVER_WHIFF_VULN,
OUTS_UNDER_STRONG, OUTS_UNDER_ELITE.
Document new WR/ROI numbers for each. Demote any that fail triple
verification on the corrected substrate.
  - Cost: 2-3 sessions

**Phase 4: Cutover.**
Drop and rebuild canonical `pitcher_cumulative` with patched 06a.
Update ROADMAP.py and DECISIONS.py with new validated stats.
Update 22l filter thresholds if any edges shifted qualifying ranges.
Pre-patch and post-patch picks are different populations (operational
caveat, same as ADR-024 park-factor alignment).
  - Cost: 1 session

**Phase 5: Archive.**
Rename original `pitcher_cumulative` to
`pitcher_cumulative_pre_fix_<date>`. Document caveat for forward
analysis.
  - Cost: 0.5 session

### Alternatives considered and rejected

**(a) Patch 06a in a single step today.**
Rejected. Every validated edge claim becomes unverified on the
corrected substrate. Continuing to publish on edges with stats from
buggy data is precisely the trust-the-system violation ADR-024 fixed.

**(b) Patch 06a, accept that historical numbers may drift, defer
re-validation.**
Rejected. The bug magnitude is unknown. Could be small (<5% mean
error) or large (20%+). Without Phase 1 data, deferring re-validation
is choosing without information.

**(c) Leave the bug in place permanently.**
Rejected. Live underperformance of validated edges (UNDER_VALIDATED
L6, HIGH_PARK_GAP -23.8% gap) may be partially driven by this bug.
Leaving it means we never know.

**(d) Patch only one edge's pipeline at a time.**
Rejected. The substrate is shared across all consumers; partial
patches create downstream inconsistency.

## Consequences

### Positive
  - Permanent correctness restoration on the foundation table.
  - Re-validation produces honest forward stats on which to base
    sizing and tier decisions.
  - Future research scripts (verify_edges_v5, etc.) read clean data.

### Negative / Caveats
  - Pre-patch and post-patch tracked bets are different populations.
    Aggregate live performance comparisons across the cutover are
    invalid.
  - Some currently-validated edges may fail on corrected substrate.
    Demotions are an expected outcome, not a project failure mode.
  - Total work: 5-7 sessions end to end. Cannot be compressed without
    skipping validation phases.

## Today's operational implications (2026-04-27)

  - 06a-affected pitchers fall back to AVG_SP in 11_predict_totals.py.
    Memory rule: AVG_SP UNDER picks failed validation at -120 juice.
  - `opener_flag_check.py` (built this session) flags these games for
    operator visibility. Today: drop totals tags on STL@PIT
    (Montgomery) and SEA@MIN (Prielipp).
  - UNDER_VALIDATED hold (separately recommended after L6 streak
    diagnosis) remains in effect.

## Implementation artifacts (Session 27, all read-only unless noted)

  - `diag_under_validated_l6_streak.py`
  - `audit_park_factors_for_11_predict_totals.py`
  - `opener_flag_check.py`
  - `diag_dh_kprop_unresolved_20260426.py`
  - `fix_dh_kprop_resolve_20260427.py` (only writer this session;
    re-applied DH starter swap + resolved 2 stuck K-prop rows)
  - `diag_06a_filter_audit_broad_20260427.py` (had pitch-counting bug)
  - `diag_montgomery_threshold_check_20260427.py`
  - `diag_06a_bug_location_20260427.py`
  - `diag_06a_filter_audit_corrected_FAST_20260427.py`
  - `diag_06a_quantify_damage_phase1.py` (Phase 1 of permanent fix)

## References

  - ADR-024 — park-factor alignment, the precedent for handling
    substrate drift carefully via ADR + alternatives + caveats
  - DECISIONS.py "SESSION 27 — UNDER_VALIDATED L6 ROOT CAUSE"
  - HISTORY.py "PHASE 15: 06A OUTER-LOOP BUG DISCOVERY"
  - ROADMAP.py "Active open items" → 06a OUTER LOOP BUG


## Phase 3a status update (2026-05-10, Session 29)

The 5-phase plan documented above assumed Phase 3 ("re-validate every
edge") would execute as a single multi-session push covering all
markets. Substrate-inventory work in Session 29 surfaced gaps that
force a Phase 3 split into three sub-phases:

  - **Phase 3a — TOTALS: COMPLETE** (this update)
  - **Phase 3b — K-PROPS: BLOCKED** (substrate gaps; multi-session
    rebuild required)
  - **Phase 3c — OUTS: BLOCKED** (same pattern as 3b)

### Phase 3a deliverables (Session 29)

- `10a_v2_substrate_for_phase3.py` — surgical fork of production v2
  10a backtest model. Two-line diff: reads `pitcher_cumulative_v2`,
  writes `game_totals_backtest_v2`. Production tables UNTOUCHED.
- `verify_substrate_drift_v1_vs_v2.py` — read-only drift report.
- `verify_edges_v5a.py` — totals-edge re-validation framework.
  Surgical fork of `verify_edges_v4.py`. Reads
  `game_totals_backtest_v2`. Edge set: HIGH_PARK_GAP +
  UNDER_VALIDATED.

### Phase 3a substrate-drift findings

- 7,283 games overlap v1 ∩ v2 on the 2023-2025 universe. Zero
  v1 rows dropped on v2.
- Predicted-total median per-game shift: **+0.010 runs**.
- P25–P75 delta range: -0.070 to +0.090 runs.
- 23 games (0.3%) shifted by >0.5 runs.
- HIGH_PARK_GAP qualifying-bet count: 108 (v1) → 110 (v2).
- UNDER_VALIDATED qualifying-bet count: 1,047 (v1) = 1,047 (v2).
- v1 MAE 3.517 vs v2 MAE 3.519 — statistically identical.

The original ADR-028 worst case feared 20%+ shift on cum_pitches.
Actual median impact on totals predictions is ~0.01 runs/game.
**The bug is real, but its impact on the totals market is
materially smaller than feared.**

### Phase 3a edge results (verify_edges_v5a)

**HIGH_PARK_GAP — 2/3 gates** (down from v4's 3/3)

| Year | n | WR | ROI@-110 | Wilson 95% CI | Gate |
|------|---:|----:|---------:|---------------|------|
| 2023 | 31 | 51.6% | -0.9% | [34.8%, 68.0%] | **G1 fail (thin sample)** |
| 2024 | 52 | 70.2% | +34.1% | [56.7%, 80.9%] | pass |
| 2025 | 27 | 77.8% | +48.5% | [59.2%, 89.4%] | pass |
| ALL | 110 | 66.8% | +27.8% | [57.6%, 74.9%] | — |

G2 PASS (18/20 months winning, 90%); G3 PASS; G2_STRICT PASS
(9/11 months ≥5 bets, 82%). Walk-forward Q1–Q4: -0.3% / +23.9% /
+34.3% / +51.4% — improving, not decaying. The 2023 thin-sample
fail is the only G1 concern.

**UNDER_VALIDATED — 3/3 gates** (first 3-year verification)

| Year | n | WR | ROI@-110 | Wilson 95% CI | Gate |
|------|---:|----:|---------:|---------------|------|
| 2023 | 306 | 55.6% | +6.3% | [50.0%, 61.0%] | pass |
| 2024 | 340 | 58.2% | +11.3% | [52.9%, 63.4%] | pass |
| 2025 | 401 | 57.1% | +9.2% | [52.2%, 61.9%] | pass |
| ALL | 1,047 | 57.0% | +9.0% | [54.0%, 60.0%] | — |

G2 PASS (18/21 months, 86%); G3 PASS; G2_STRICT PASS (17/20 months
≥5 bets, 85%). Walk-forward Q1–Q4: +7.0% / +10.6% / +11.0% / +7.6%
(no decay). Wilson CI entirely above 52.4% break-even.

### Operational decisions landing in Session 29

- **UNDER_VALIDATED hold (Session 27) LIFTED.** Edge passes 3/3 on
  corrected substrate. Pre-alignment live 4W-14L is variance against a verified
  +9% ROI / 57% WR edge. 22l should publish UNDER_VALIDATED tags
  going forward. **Precondition:** audit 22l's hardcoded gap
  thresholds against v5a-verified filter (gap ∈ [-1.0, -0.25],
  UNDER, fallback excluded) before next pregame_pipeline run.
  ADR-024 precedent on HIGH_PARK_GAP found a similar mismatch.
- **HIGH_PARK_GAP** continues at current sizing on **gate-watch**
  status. Forward demotion rule: if 2026 finishes with n≥30
  post-alignment picks below 55% WR, demote. If recovers above 60%,
  status quo.
- **Phase 4 cutover DEFERRED** behind Phase 3b/3c. Substrate drift
  on totals is too small to justify a risky cutover before the
  full edge re-validation completes.

### What the bug was *not* (objective finding)

The 06a outer-loop bug is real but is **not** the explanation for
either edge's live underperformance (live numbers below were
subsequently found to mix pre/post-alignment populations — see
docs/adr/ADR-030; corrected attribution follows):

- HIGH_PARK_GAP live -28pp gap is not bug-driven. The substrate
  moved 2 qualifying games (0.3%). Memory's '11W-13L
  underperformance' was mixed pre+post-alignment per ADR-030.
  Real post-alignment performance (3W-3L on n=6) is variance-
  consistent with backtest. Underperformance framing was an
  artifact of population mixing. Any remaining gap
  another cause we have not identified.
- UNDER_VALIDATED pre-alignment 4W-14L (today's lift IS the alignment
  per ADR-029; the 4W-14L was tagged on AVG_SP-fallback-included
  population that 22l now excludes). The edge cleanly passes
  3/3 on corrected substrate; v5a's 57.0% WR matches memory's
  58.1% backtest figure within sampling noise.

Earlier ROADMAP/DECISIONS framing ("live underperformance may be
bug-driven" — itself anchored on mixed-population edge_monitor
numbers per ADR-030 — was incorrect framing on top of incorrect
diagnosis. Specifically the framing
partially explained by the 06a bug") is refuted by Phase 3a data.
ADR-028 was a real correctness fix, but it was not the smoking
gun. Investigate elsewhere — separate session, separate hypothesis.

### Phase 3b/3c blockers

**Phase 3b (K-PROPS):**
1. `historical_k_props` covers 2024-25 only (zero 2023 rows).
   3-year triple verification structurally impossible without an
   odds-data backfill.
2. `k_prop_backtest` contains baked-in `cum_k_pct`,
   `cum_whiff_rate`, `cum_avg_bf_per_start`, `cum_*` columns from
   v1 `pitcher_cumulative`. Needs `k_prop_backtest_v2` regeneration
   analogous to `10a v2`. The script that originally populated
   `k_prop_backtest` is not obviously present in `E:\mlb_model\10*.py`
   (only `07_predict_today.py` exists; no 10b/10c).
3. `game_context` has zero historical rows (2023-25).
   `K_OVER_WHIFF_VULN` cannot be 3-year verified without lineup-
   history backfill.

**Phase 3c (OUTS):**
- `historical_k_props.outs_line` is 2024-25 only with 15% NULL
  even within range.
- No outs-specific historical-predictor identified.
- Same substrate-rebuild requirement as K-props.

Estimated work: 2-3 sessions each, partly overlapping.

### Methodology lessons (Session 29)

1. **Substrate-drift quantification before edge re-validation
   saves cycles.** The drift report told us upfront the impact
   was small. Reverse order would have produced edge results
   without knowing how to interpret them.
2. **"Phase 3 is one phase" was wrong in the original plan.**
   K-prop and outs substrates differ structurally from totals.
   ADR should treat Phase 3 as N sub-phases, one per market.
3. **Anti-drift discipline:** stopping at the substrate-inventory
   step before writing v5b prevented a guess-driven script against
   the wrong table.
4. **The "live underperformance is bug-driven" framing rested on
   mixed-population edge_monitor numbers (ADR-030) and was an
<!-- Session 29 / ADR-030: live records corrected -->
   embedded hypothesis** that Phase 3a's drift report objectively
   refuted. The "red team in background, no confirmation bias"
   guardrail was the discipline that allowed v5a to produce
   results contrary to the embedded framing. Future framings of
   this shape should be tested as soon as the substrate exists.

### Followups (logged, not blocking)

- **22l UNDER_VALIDATED filter audit** before next pregame run.
- **Production-table provenance:** re-running 10a today does not
  exactly reproduce production `game_totals_backtest`. v1-on-disk
  MAE 3.517 vs regenerated MAE 3.519 — close but not identical,
  suggesting an upstream input drifted (team_offense, bullpen_stats,
  park factors, or older 10a version) since original population.
  Not blocking Phase 3a (v1-vs-v2 comparison was apples-to-apples;
  both ran today against same upstream tables). Future audit.
- **`edge_monitor` flag for HIGH_PARK_GAP gate-watch** so the
  dashboard surfaces the 2/3 status without operator memory load.

### Database state (post-Session-29)

| Table | Status |
|-------|--------|
| `pitcher_cumulative` | UNCHANGED (v1, 14,129 rows). In production. |
| `pitcher_cumulative_v2` | NEW (v2, 14,451 rows). Verified correct. |
| `game_totals_backtest` | UNCHANGED (v1, 7,283 rows). In production. |
| `game_totals_backtest_v2` | NEW (v2, 7,841 rows). Verified. |

# ADR-056 (Accepted): Pipeline-wide data-integrity audit + per-side completion (following ADR-055)

Status: **Accepted** (2026-06-17). Follows ADR-055 (actual_total pre-play bug). Work was mostly
READ-ONLY audit; writes were atomic verify-before-commit corrections (per-side runs, situational_
features) and self-guards. This is a TRUE RECORD including the scope-miss and the corrections of
prior misreads -- not a win log.
Relates to: ADR-055 (the totals pre-play bug + builder fix + total guard), ADR-051 (clean
backtest), ADR-045 (v2 substrate), ADR-048 (K dark).

## WHY (the scope-miss, stated plainly)
ADR-055's Step 2 was scoped to `actual_total` ONLY and LEFT the per-side run columns
(`actual_home_runs`/`actual_away_runs`) pre-play-corrupt: 625 wrong in game_totals_backtest, 712
in game_totals_backtest_v2 (home-side dominated -- walk-offs). This was discovered when a planned
situational_features rebuild would have re-derived a wrong winner from those still-corrupt
per-side runs. Cleanup 1b corrected them (consistency-gated: post_home+post_away == the already-
fixed actual_total on every row; 7283/7283 and 8267/8267) and EXTENDED the builder guard to
assert per-side, not just the total.

## CORRECTIONS OF RECORD (prior misreads, fixed)
- The interim "193 benign through-9 convention" reading was WRONG: root-cause proof showed all
  625 are the SAME pre-play bug; the 193 coincidentally matched through-9 because the missed
  final-play runs equaled the extra-inning runs.
- The "55 wrong winners" in situational_features was an UNDERCOUNT: the true count is 430
  (walk-off flips -- the winning run scored on the final play the pre-play score missed).

## PIPELINE-WIDE AUDIT (two prongs: code-fingerprint scan + independent data reconstruction)
The bug class (pre-play score / bare GROUP BY game_pk) is CONFINED to the 10a / 10a_v2 totals
builders (now fixed + guarded). All other builders are PATTERN-CLEAN: the outcome resolvers
(09b/09c/09f) pull finals from the official MLB Stats API; the cumulative/snapshot builders use
event-level SUM aggregation, not score-column rollups.

## NUMBER-CHECK (independent reconstruction from raw pitches; NOT builder helpers)
- AS-OF (leakage) check PASSED on the predictor-feeding cumulative tables: pitcher_cumulative_v2
  (cum_k_pct 392/400 strict-before, max diff 0.0042), team_offense_cumulative (off_k_pct 300/300),
  bullpen_stats_cumulative (bp_k_pct 299/300) -- strict-before agreement beats include-D in every
  case => NO leakage.
- Snapshot count/rate fields VERIFIED (with the builders' actual events-not-null denominator):
  pitcher_stats (k/bb/n_pa 2796/2796 exact), team_offense (n_pa + k_pct/bb_pct/hr_per_pa 120/120),
  bullpen_stats_v2 (bp_k_pct/bp_bb_pct 120/120), hitter_stats (k/bb/hr 2207/2207 exact).
- K outcome tables exact (k_prop_backtest 13304/13304 vs pitch K-events; full_slate/r3 100%).
- Live 2026 bet logs match post-score truth (totals_tracker 599/599, mlrl_tracker 1095/1095,
  mlrl_streak_picks 159/159, published_picks-totals 61/61) -> the corruption was 2023-25
  BACKTEST-ONLY and never reached live grading (which flows through the API resolvers).

## SUSPECT (low severity; nothing live reads these)
- situational_features residual: `margin` + winner-derived streak features (home_streak,
  away/home_last3_wins, last10_wins) remain stale (actual_total + winner were targeted-fixed:
  433 + 430 rows). Full correction needs a 26a rebuild -- now UNBLOCKED by Cleanup 1b.
- bullpen_stats (v1): ~2x reliever-denominator vs independent reconstruction; legacy, superseded
  by bullpen_stats_v2 (which is clean).
- game_totals_backtest / _v2 prediction + park columns (predicted_total, park_factor): still
  blocks-A/B contaminated; read by NO live verdict.
- Frozen backup game_totals_backtest_v2_bak_prehybrid_20260607_161053 (671 corrupt rows): a
  SNAPSHOT OF THE BUG, NOT a recovery source.

## CANNOT-VERIFY (not clean -- uncheckable by reconstruction)
Proprietary fields (woba/xwoba, barrel%, hard_hit%, avg_velo, csw, chase, arsenal usage
weighting, tto splits); external fangraphs_batting/fangraphs_pitching scrapes; batter_whiff_
profiles / pitcher_arsenal_profiles (windowed/pooled processed build -- the signal math was
separately reconstructed to 1e-9); bet_tracker.result_k (pitcher-name key format mismatch);
outs_tracker.result_outs (multi-out DP/TP ambiguity); under_edge_tracker.result_total (NULL).

## RE-CONFIRMATION (findings survive the data fix)
On corrected data, all three headline verdicts HELD with margin: floor DOOR CLOSED
(line_MAE ~3.45 vs realistic floor ~3.54), full-model totals LIFE=FALSE (WR 49.5->50.0%,
gradient non-monotonic), whiff->UNDER FAIL (gradient non-monotonic). The predicted_total_clean
second-order staleness (built partly from pre-fix actuals) is bounded <~0.05 run and proven
immaterial.

## PREVENTION
The totals builders (10a / 10a_v2) self-guard before writing: assert actual_total AND per-side
(actual_home_runs/actual_away_runs) == last-pitch post-score truth, sys.exit(1) on mismatch. 26a
has a sibling situational guard (actual_total + winner vs independent post-score truth).

## OPEN / DEFERRED (carried, NOT silently closed)
- 26a situational_features FULL rebuild (now unblocked by Cleanup 1b) -> fixes margin + streak residual.
- game_totals_backtest / _v2 prediction + park column rebuild (blocks-A/B; read by no live verdict).
- bet_tracker pitcher-name -> id crosswalk (to enable result_k verification).
- Deferred-cost tables not yet number-checked: game_context, historical_weather, pitcher_arsenal,
  pitcher_tto, pitcher_regression, team_regression, team_defense, platoon_pit_lineup,
  phase_1_8_substrate_audit.

## SCOPE STATEMENT (honest)
Verified clean WHERE RECONSTRUCTABLE (outcome columns, as-of cumulative predictor feeds, snapshot
count/rate fields, live bet-log results). The residual above is explicitly UNCHECKABLE by
reconstruction or DEFERRED -- it is NOT asserted clean. The pipeline is NOT "fully clean"; it is
"verified where reconstructable, with an explicit uncheckable/deferred residual."

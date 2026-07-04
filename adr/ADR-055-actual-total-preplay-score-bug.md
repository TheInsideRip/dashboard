# ADR-055 (Accepted): actual_total corruption from pre-play score selection in the totals backtest builders

Status: **Accepted** (2026-06-17). Diagnosis was READ-ONLY; the fix edited two builder source
files and corrected three live tables under atomic verify-before-commit (Steps 1-4). Outcome:
a real data-integrity defect found, proven via the official MLB Stats API, corrected, and made
non-recurring by a fail-safe guard.
Relates to: ADR-051 (clean-substrate totals re-validation -- its actual_total inputs were among
the corrupt rows; see RE-CONFIRMATION), ADR-024 (park factors), ADR-045 (v2 substrate),
ADR-052 (edge-test floor). Supersedes the in-session "193 benign through-9 convention" read
(see CORRECTION).

## BUG
The totals backtest builders selected bare, non-aggregated `home_score`/`away_score` from
`pitches_historical` via `GROUP BY game_pk` (no aggregate, no ORDER), then set
`actual_total = home_score + away_score`. Those columns are the per-pitch live score BEFORE the
play (SCHEMA gotcha); the bare-column GROUP BY returns the last-scanned pitch's pre-play score,
which MISSES the runs scored on the final play. Result: a one-directional LOW error,
+1-dominant (77% off by exactly +1; remainder +2..+4 for multi-run/grand-slam final plays),
present in 9-inning walk-offs as well as extra-inning games. Locations: 10a / 10a_v2
`extract_games` (the actual_total source) AND the league-average and park-factor subqueries
(blocks A/B), all using the same pre-play pattern.

## DETECTION (the unflattering part)
The bug surfaced ONLY because a First-5-innings reconstruction probe cross-checked the game
total a SECOND way (sum of last-pitch `post_*_score`) and disagreed with `actual_total` on
8.58% of games. **ROOT LESSON: nothing ever validated the outcome column against an independent
source.** The "clean" leak-corrected substrate (game_totals_backtest_clean) was leakage-clean on
its inputs but its outcome column was wrong; "clean" did not mean correct. The defect had
persisted across multiple sessions undetected.

## PROVEN SCOPE (MLB Stats API as third source, 625/625 adjudicated)
The official MLB Stats API (statsapi.mlb.com linescore) adjudicated all disputed games: the
last-pitch post-score reconstruction == API final for 625/625; `actual_total` was the outlier
every time. Corrupt actual_total rows:
- game_totals_backtest_clean: 625 rows
- game_totals_backtest_v2: 712 rows
- game_totals_backtest (source, built by 10a): 625 rows
The frozen backup `game_totals_backtest_v2_bak_prehybrid_20260607_161053` holds 671 corrupt rows
-- it is a SNAPSHOT OF THE BUG, NOT a clean recovery source; it must not be used to "restore."

## CORRECTION TO A PRIOR READ (recorded honestly)
An interim adjudication labeled 193 extra-inning mismatches as a "benign through-9 / regulation
convention" (because their `actual_total` equaled the API through-9 total). The root-cause proof
showed this was WRONG: ALL 625 (including those 193) are the SAME pre-play bug. The 193
coincidentally matched through-9 because, for those extra-inning walk-offs, the missed final-play
runs happened to equal the extra-inning runs. There is no intentional convention.

## FIX
- Builders corrected (Step 1): 10a_game_totals_model.py and 10a_v2_substrate_for_phase3.py now
  select the SINGLE last pitch per game_pk via ROW_NUMBER() OVER (PARTITION BY game_pk ORDER BY
  at_bat_number DESC, pitch_number DESC)=1 and take post_away_score+post_home_score from that
  same row -- applied to extract_games AND the league-average + park-factor subqueries.
  Proven: regenerates the API finals 1337/1337 on the known-corrupt rows, 0 previously-correct
  rows broken.
- Tables corrected (Step 2): 1962 actual_total rows corrected (625 + 712 + 625) under
  per-table backup -> BEGIN -> UPDATE actual_total only -> whole-table verify (0 disagree, row
  count unchanged, checksum of every other column == backup) -> COMMIT. All three committed.
- predicted_total_clean was built through the AS-OF path (live predict_runs_for_side fed by
  as-of cumulative league/park computed strictly-before game_date) and NEVER touched the
  pre-play blocks A/B; only its actual_total was wrong, now fixed. No prediction rebuild needed.

## RE-CONFIRMATION (findings survive the fix)
Re-run on corrected game_totals_backtest_clean (Step 3), all HELD with margin:
- FLOOR: line_MAE 3.468 -> 3.448, realistic floor ~3.54, headroom ~ -0.09 -> DOOR CLOSED.
- FULL-MODEL TOTALS: base-rate WR 49.54% -> 49.99% (still ~2.4pt below 52.38% breakeven),
  disagreement gradient still non-monotonic -> LIFE=FALSE.
- WHIFF->UNDER (A): discovery residual gradient still non-monotonic -> FAIL.
The second-order staleness (predicted_total_clean's as-of league/park were derived partly from
the pre-fix actuals) is proven immaterial -- all verdicts hold with margin.

## PREVENTION
Both builders now run a fail-safe guard immediately before the to_sql write: it independently
reconstructs last-pitch post-score truth (a SEPARATE query, not the builder's own SELECT),
asserts built actual_total == truth for every game_pk, prints GUARD PASS/FAIL, and sys.exit(1)
on any mismatch -- so a failing build writes nothing and leaves the existing table intact.
Smoke-tested: a deliberately-wrong row triggers exit(1); a correct row passes (both files).

## OPEN / DEFERRED
The prediction and park columns in game_totals_backtest and game_totals_backtest_v2 remain
contaminated by the (now-fixed) blocks-A/B pre-play league/park subqueries. They are read by NO
live verdict (the Step-3 verdicts read only game_totals_backtest_clean), so their rebuild is
DEFERRED, not done here. If anything live begins reading those columns, rebuild both tables with
the corrected (post-score, as-of) builders -- the guard will enforce a correct actual_total on
that rebuild.

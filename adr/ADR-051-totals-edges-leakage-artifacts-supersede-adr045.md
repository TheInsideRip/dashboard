# ADR-051 (Accepted): Totals edges HIGH_PARK_GAP + UNDER_GAP are leakage artifacts; SUPERSEDES the ADR-045 totals re-validation

Status: **Accepted** (2026-06-16). READ-ONLY investigation; built as-of substrate tables and a
clean backtest, no serving/builder/tagger code changed, no live DB rows mutated. Outcome:
the two "validated" totals edges VANISH on leak-clean data.
Relates to: ADR-045 (v2 substrate cutover + totals re-validation -- the re-validation this ADR
supersedes), ADR-035 (totals edge beats retail not sharp -- corroborated), ADR-024 (park
alignment), ADR-043/047 (v2 substrate provenance).

> All row counts, table existence, and the clean-vs-leaky correlation were verified first-hand
> against the live DB on 2026-06-16. ROI/WR re-validation figures are attributed to
> build_clean_backtest_revalidate_20260616.py output (clean_backtest_revalidate_OUT.txt).

## Root cause -- the leak
`team_offense` (**120 rows**, verified) and `bullpen_stats_v2` (**120 rows**, verified) are
SEASON-FINAL snapshots keyed only to a game's own season. The totals backtest scored midseason
games with full-season offense/bullpen inputs -- i.e. it used end-of-season knowledge to predict
games played earlier that same season. `pitcher_cumulative_v2` (15,732 rows) was already a proper
as-of (strictly-before) table and was NOT the source of the leak.

## Fix -- as-of substrate + clean backtest
- Built `team_offense_cumulative` (**16,526 rows**, verified) -- strictly-before season-to-date
  team offense, season-reset, vsL/vsR platoon splits, 50-PA floor + league prior.
- Built `bullpen_stats_cumulative` (**16,427 rows**, verified) -- relievers-only, strictly-before
  season-to-date bullpen, vsL/vsR on batter stand.
- Rebuilt `game_totals_backtest_clean` (**7,283 rows**, verified) by importing the LIVE model's
  `predict_runs_for_side` on as-of inputs. Formula-reproduction gate: max |imported - inline
  reproduction| = 0.00000 over 20 side-calcs (per clean_backtest_revalidate_OUT.txt, 3.0 GATE
  PASS). 0 leakage by construction (every input strictly before game date).

## Apples-to-apples result (same games / line / gap; only predicted_total timing differs)
Per build_clean_backtest_revalidate_20260616.py output, 2026-06-16:
- **HIGH_PARK_GAP (OVER):** stored ROI **+19.8%** -> clean **-8.7%**. Every season flips
  positive->negative (2024 +25.3% -> -8.7%; 2025 +19.8% -> -3.0%).
- **UNDER_GAP (UNDER):** stored ROI **+6.8%** -> clean **-2.5%**.
- Clean model correlation with actual totals **0.1101** vs leaky/stored **0.1816** (verified
  first-hand from `game_totals_backtest_clean`: `predicted_total_clean` 0.1101, `stored_pred`
  0.1816, 2026-06-16). The leak inflated apparent accuracy.

## What this supersedes (EXPLICIT)
This **SUPERSEDES the ADR-045 totals re-validation** (ADR-045 "Evidence the cutover is correct":
HIGH_PARK_GAP "69.7% WR, n=76, RE-VALIDATED 3/3"; UNDER_GAP "55.2% WR, n=1,558, RE-VALIDATED
3/3"). That re-validation ran on the leaky season-final `team_offense` / `bullpen_stats_v2`
tables and is **no longer authoritative for these two edges**. ADR-045's other conclusions
(the v2 serving cutover itself, the outs demotion) are unaffected. This corroborates ADR-035
(the totals edges beat the retail/median line, not a sharp/clean baseline) and ADR-045's own
ADR-035 line-basis caveat.

## Consequence
HIGH_PARK_GAP and UNDER_GAP should **not** be treated as validated edges. This ADR is the
evidentiary record; the operator controls publishing -- it is not itself a publish block.

## Minor residual noted
`bullpen_stats_cumulative.bp_n_pa` differs ~1.3% from `bullpen_stats_v2` (a definitional PA
boundary difference); the rate stats match within 0.0003. Not material to the verdict.

# ADR-035: Totals Validated-Edge Filters — Edge Was Against Retail, Not Sharp

**Status:** Accepted
**Date:** 2026-05-24 (Session 37)
**Supersedes:** None. Reframes (does not supersede) the drawdown
                investigation arc opened in Session 32 and reframed
                in ADR-034 (Session 36).

## Context

Drawdown investigation since Session 32 has cycled through hypotheses
about predictor bias, train/serve divergence, substrate corruption,
and league regime shifts. Session 36 closed the lineup-composite
lead (ADR-034). Going into Session 37 the leading hypothesis was
"low-tier prediction bias" in the 7.5-8.5 predicted_total tier.

Session 37 systematically retired all predictor-bias hypotheses,
then established that the live problem is **selection bias** at the
tag-firing layer, not predictor bias.

## Decision

Three findings, each independently verified this session:

1. **The model is unbiased on the full 2026 slate.** Drift study
   `diag_drift_study_step1a_totals.py` (built Session 35, run for
   the first time Session 37): bet universe bias +0.063 runs,
   full slate bias -0.122 runs, gap +0.185 runs. Tagged games are
   the games the model is most wrong about, not a problem with
   the model in aggregate.

2. **Validated edges work historically — against retail books.**
   On 3-year `historical_odds` (DK/FD-driven) substrate:
   UNDER_VALIDATED 55.6% WR (n=1,291, CI [52.9%, 58.3%]),
   HIGH_PARK_GAP 67.2% (n=122, CI [58.5%, 74.9%]). Both within
   backtest CIs.

3. **The same filters fail against Pinnacle (sharp) closing lines
   for every year 2023-2026.** On `pinnacle_historical_odds`
   substrate (Session 21 backfill + Session 37 2026 backfill,
   averaged across all snapshots per game):

     ```
     UNDER_VALIDATED (gap 0.25-1.0):
       2023: 46.3% WR (n=451)
       2024: 46.3% (n=374)
       2025: 42.6% (n=462)
       2026: 39.2% (n=79)

     HIGH_PARK_GAP (gap>=1.3, AZ/BOS/COL/WSH):
       2023: 34.4% (n=32)
       2024: 65.1% (n=63)
       2025: 63.9% (n=36)
       2026: 37.5% (n=24)
     ```

   UNDER_VALIDATED never beat coinflip on Pinnacle in any of
   four years. HIGH_PARK_GAP wins on Pinnacle in 2024-25 only.

## Implication

The validated edges measured in DECISIONS.py never beat sharp
closing lines. They beat retail-book closing lines that had
moved away from sharp (likely retail demand or square-money
bias creating retail/sharp gaps). When the model predicted
UNDER and retail was higher than sharp, the bet hit because
sharp had it right.

This is not a model edge in the sense of "the model knows
something the market does not." It is a market-structure edge:
"retail books mispriced relative to sharp." Whether that
mispricing exists in 2026 retail books is the real question,
and `totals_tracker.book_line` (selection-biased) is the
only 2026 retail substrate we currently have. Phase 1.8 (next
session) is retail-vs-Pinnacle gap by year.

## Evidence and rejected explanations

`diag_phase1_5_selection_bias_v2.py` (Phase 1.5): both filters
survive 3-year revalidation on historical_odds substrate
(retail-driven). Backtest claims hold.

`diag_phase1_6_selection_decomposition.py` (Phase 1.6):
on 2026 tagged games, tag_bias diverges from same-date
slate_bias by +1.408 runs (HIGH_PARK_GAP) and -2.499 runs
(UNDER_VALIDATED). Selection mechanism picks games where the
model is dramatically more wrong than its slate-wide average.

`diag_phase1_7_vegas_sharpness_v3.py` (Phase 1.7): Pinnacle
book MAE 2023 3.471, 2024 3.240, 2025 3.455, 2026 3.311.
Pinnacle is **not** meaningfully sharper in 2026 than in
prior years. The original "books got sharper" hypothesis
is rejected. The filters never had an edge on sharp lines,
in any year.

Rejected within this session:
- "Books got sharper in 2026" (no; Pinnacle MAE flat across years)
- "Model regime change in 2026" (no; full slate bias -0.19 within
  noise of 2023-25)
- "Pitcher cumulative substrate drift v1->v2" (no; delta +0.007 runs)
- "Lineup composite divergence" (no; rejected previously per ADR-034)
- "Baseline staleness is the dominant cause" (partial only; +0.143
  runs of measured bias, not the dominant cause; left unpatched
  per "no point fixing predictor if filter is the issue")

## Consequences

### For publishing
- HIGH_PARK_GAP and UNDER_VALIDATED *may still work in 2026* if
  retail books still have the gap-to-sharp that historically
  existed. Cannot confirm without 2026 retail full-slate substrate.
- Continue current operational holds. Live tags continue
  publishing per existing ADRs (032, 033) because the surviving
  alternative is "publish nothing while we figure out retail-vs-
  sharp gap."

### For modeling
- Predictor rebuild is not the right next step. The model
  produces an honest expected value on full slate. The
  publishing logic (gap-vs-book threshold) is what is
  selection-biased.
- Baseline staleness bug (+0.143 runs from multi-year pooling
  in `compute_league_averages` and `load_park_factors`) is
  real and present but not the dominant cause. Logged for
  future cleanup, not patched.
- TOTALS_REBUILD_PREREG_001 (drafted earlier in Session 37)
  is **withdrawn**. The scope it pre-registered (predictor
  patches against bias) is wrong. The actual question is
  filter recalibration, which requires data not yet on hand.

### For data infrastructure
- `historical_odds` table frozen at 2025-09-28 (pipeline stopped
  loading after 2025 season). Logged hygiene item.
- `pinnacle_historical_odds` frozen at 2025-10-01 prior to
  Session 37 backfill, now extended through 2026-05-24.
  Logged hygiene item: daily pipeline that populates pinnacle
  is not running for 2026.
- Daily odds pull populates `game_odds_lookup` (ML only).
  Full-slate totals lines for non-published games are not
  persisted from the daily pull. Future-day blind spot.
- Session 37 2026 backfill used different `snapshot_slot`
  names than Session 21 (`near_closing` vs `evening_preclose`,
  etc). Schema-level naming drift; not data corruption.
  Future diagnostics joining across years must accommodate.

### For methodology
- Pre-reg drafting *should* check substrate availability
  before committing to gates. Pre-reg work was done in
  Session 37 against 2026 retail substrate that does not
  actually exist. Document the substrate check as part of
  pre-reg drafting.
- Triple verification on historical substrate, when that
  historical substrate is itself biased (retail-only or
  partial book coverage), is not sufficient to confirm
  edge. Must include verification against sharp substrate
  (Pinnacle) where available.

## Action items, queued

1. Phase 1.8: retail-vs-Pinnacle gap by year. Substrate:
   `historical_odds` (retail) vs `pinnacle_historical_odds`
   (sharp) for 2023-25. For 2026 use `totals_tracker.book_line`
   (selection-biased, accept that limitation).
2. Daily pull patch: persist totals lines for full slate to
   a new table, not just for tagged games. So that future
   substrate exists.
3. Backfill hygiene: reconcile 2026 snapshot_slot naming to
   Session 21 conventions via mapping patch script.
4. Quarantine ~227 specialty-market rows (line outside 5-14)
   in 2026 pinnacle data per Session 21 precedent.
5. Baseline staleness patch (low priority, logged for cleanup).

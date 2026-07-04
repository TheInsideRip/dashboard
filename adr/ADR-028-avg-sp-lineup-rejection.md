# ADR-028: AVG_SP × LINEUP Study — Pre-Reg Rejection

**Status:** Accepted
**Date:** 2026-04-26 (Session 26)
**Pre-registration:** AVG_SP_LINEUP_PREREG_001 v1.0 + v1.1 amendment

## Context

The AVG_SP × LINEUP study tested whether combining "average-tier
starting pitcher" (xwOBA Q25-Q75 rolling 365d) with "lineup at
platoon disadvantage" (rolling 30-day platoon wOBA in bottom quartile
vs SP hand) produces a totals UNDER edge surviving 3-year triple
verification.

This was a directed re-examination of two signals previously rejected
as standalone OVER edges in Session 19 (platoon wOBA at -10.4% ROI on
n=716; arsenal mismatch at -7.2% ROI on n=716). Session 19's exception
clause permitted re-test only when a third stabilizing variable could
plausibly rescue them. SP tier was that candidate variable.

The study was the first project research effort to follow the full
pre-registration discipline from blank slate: pre-reg drafted before
any code, locked v1.0, amended to v1.1 BEFORE any analytical script
ran (schema-discovery-driven, not results-driven), then executed
with a 144-cell sweep across 3 SP-tier definitions. Phase 0
prerequisites — point-in-time platoon and whiff utilities — were
built and verified before Phase 1a.

Pre-registration components:
- 48 cells per SP-tier definition (3 sides × 2 signals × 2 directions × 2 SP tiers)
- 8 verification gates per cell (G1 year-split, G2 monthly stability,
  G3 -120 juice, G4 peak-month removal, G5 recent decay, G6 bootstrap CI,
  G7 baseline lift ≥+3.0pp, G8 Wilson CI > break-even)
- 4 baseline contrasts (AVG-SP-alone, matchup-alone, NON_AVG×matchup,
  market-baseline)
- Sample-size floor n≥100 per cell
- 3 SP-tier definitions (PRIMARY = xwOBA, ALT1 = K-BB%, ALT2 = composite)
- Robustness rule: cell passing on PRIMARY must hold direction with
  ROI ≥ +1.0pp on Alt 1 AND Alt 2

## Decision

All cells REJECTED. The AVG_SP × LINEUP hypothesis does not survive
the pre-registered verification framework.

PRIMARY (xwOBA Q25-Q75): 0 cells passed 8/8 gates. Top performer was
HOME_PLATOON_UNDER_AVG (n=681, 55.8% WR, +6.5% ROI @-110) at 6/8
gates — failed G6 (bootstrap CI lower bound -0.76%) and G8 (Wilson
CI lower bound 52.0% vs break-even 52.4%). EITHER cell at +5.04% ROI
failed G7 by only +2.12pp lift over matchup-alone baseline (threshold
was +3.0pp).

ALT1 (cum_k_bb_pct middle tertile): 0 cells passed 8/8. Top cell at
5/8.

ALT2 (composite percentile rank averaging xwOBA, K%, BB%): 1 cell
passed 8/8 (EITHER_PLATOON_UNDER_AVG, n=1284, 56.9% WR, +8.54% ROI).
However, ALT2 is not independent of PRIMARY — the composite includes
xwOBA as one of three weighted components. Per pre-reg Section 13,
alternates serve as robustness checks AGAINST a primary-cell survivor;
they cannot substitute for a failed primary.

## Decision rationale

**Why ALT2's 8/8 cannot rescue the study.** The pre-reg's robustness
rule reads: "Any cell that passes 8/8 on the primary must also show
same direction with ROI ≥ +1.0pp @ -110 on Alt 1 AND Alt 2." This
rule is structured around primary→alternates dependency. Reversing
it (alternates→rescue primary) is the textbook multiple-comparisons
trap the pre-reg was designed to prevent. Across 3 SP definitions ×
48 cells = 144 tests, finding one passer in the alternates is
statistically expected even if no real signal exists.

**Why G7 was the gating failure.** The +3.0pp baseline-lift threshold
required the AVG_SP × matchup interaction to add at least 3 percentage
points of ROI beyond what the matchup signal produces on its own (any
SP). The matchup-alone baseline came in at +2.92% ROI. The interaction
cell came in at +5.04% — a real lift of +2.12pp, but below threshold.

This is the single gate where deeper baseline analysis was most
informative. Baseline 3 (NON_AVG × matchup, the kill-switch control)
showed the interaction IS real: NON_AVG_SP × matchup produced -1.44%
to -1.85% ROI in PRIMARY cells. The SP-tier conditioning is
mechanistically valid. But the lift over matchup-alone was insufficient.

**Holdout test on frozen 2023-24 thresholds.** A separate analysis
froze the SP and platoon thresholds using only 2023-24 data and
applied them to 2025. Threshold drift between frozen and pooled
3-year cutoffs was minimal (<0.003 across all four). 2025 came in at
+7.91% ROI on n=506 (56.5% WR), which is stronger than the training
period's +2.78%. Wilson 95% CI on the holdout: [52.2%, 60.8%], with
the lower bound just below the 52.4% break-even line.

This adds independent evidence the signal is not a threshold-leakage
artifact, but does NOT override the pre-reg's strict bar.

**Mechanism.** Descriptive analysis confirmed the signal operates
through contact-quality reduction, not strikeouts. Cell games average
8.56 actual runs vs 8.89 in non-cell — a 0.33-run reduction. Cell SP
K% (22.4%) and actual K-counts per start (5.19) are statistically
identical to non-cell. The signal is "lineups make weak contact
against this hand vs an average-quality SP" — runs suppressed, K-rate
unchanged. This disconfirms a separately-testable K-prop UNDER edge
in cell games.

Seasonal distribution is uniform (15-19% per month, Apr-Sep),
disconfirming weather-signal confounding.

## Alternatives considered and rejected

**(a) Lower the +3.0pp G7 threshold to +2.0pp post-hoc, allowing
PRIMARY to pass.** Rejected. Modifying gate thresholds after seeing
results is the exact failure mode pre-registration prevents. The
+3.0pp number was set in v1.0 before any code touched the data.

**(b) Reframe ALT2's 8/8 as the primary verdict.** Rejected. The
pre-reg explicitly designated PRIMARY (xwOBA) as the locked
specification. ALT1 and ALT2 served as definition-sensitivity checks.
Treating the most permissive alternate as the de facto primary
inverts the robustness rule's purpose.

**(c) Deploy at small size as a "tracked" tier independent of
validated edges.** Considered seriously. The disciplined argument for
this: holdout test passed with +7.91% ROI on independent 2025 data,
mechanism is coherent, signal is not a known-failed baseline subset.
The argument against: this is a structural change (new edge tier
with promotion/demotion criteria) being motivated by one signal that
failed pre-reg, which is the wrong order. Build the framework first
on its own merits, then evaluate which signals qualify. Deferred to
roadmap, not implemented as part of this rejection.

**(d) Forward-test on 2026-to-date data and revisit.** Attempted.
Discovered `game_totals_backtest` and `historical_odds` totals tables
have 0 rows for 2026 dates. Forward verification deferred until those
substrate tables are populated. No hand-rolled parallel substrate
(risk of inconsistency vs the 2023-2025 backtest substrate).

## Consequences

### Positive

- Pre-registration discipline held under pressure of an interesting-
  looking result. The framework's purpose (preventing post-hoc
  reasoning) was demonstrated, not eroded.
- Identified that the Phase 6c "Under gap 0.25-1.0" edge (memory
  entry: 57.7% WR, +9.3% ROI on n=788) is a 2-year-only finding that
  fails at 3 years (-4.59% ROI on n=2,109). This edge was never
  re-validated by Session 19's verify_edges_v4 work; this study
  surfaces it as a 2-year artifact requiring DECISIONS.py annotation.
- Built durable research infrastructure: `build_platoon_join.py`,
  `build_whiff_pit.py`, `verify_whiff_pit.py`, plus the
  `platoon_pit_lineup` and `whiff_vuln_pit` PIT staging tables.
  These are reusable for future totals research.
- Disconfirmed three plausible-but-wrong hypotheses about the
  signal: (i) it's a K-prop edge in disguise, (ii) it's a cold-month
  weather signal, (iii) it's threshold-fitting noise.

### Negative / Caveats

- The signal's holdout-test result (+7.91% on 2025) leaves a
  legitimate analytical question unanswered: is this a real but
  weak signal that happened to fail pre-reg by margin, or is it
  noise that ended high? Pre-reg discipline says treat as failed
  until forward data confirms. This is the correct call but is
  not a confidence-100 call.
- The mechanism we identified (contact-quality reduction in
  AVG_SP × low-platoon-lineup matchups) is structurally plausible.
  If correct, future similar matchup-conditioning studies may
  benefit from this finding. We do not currently use it.

### Methodology lessons (added to DECISIONS.py)

1. **Default to train/test split with most recent year held out**,
   even under pre-registration. Pre-reg + holdout is stronger than
   pre-reg alone. Phase 1a used "all-data triple verification" per
   Session 19's verify_edges_v4 convention. The Session 19 lesson
   from ML_BP_EXHAUST should have been "always include a holdout
   year," not "always include all data." This study took the wrong
   half of the lesson.

2. **Substrate availability check (forward-test data) belongs in
   pre-reg drafting**, not after Phase 1a completes. Discovery that
   2026 backtest tables were unpopulated should have been part of
   Phase 0, not a post-hoc discovery during attempted forward
   verification.

3. **Schema discovery before any SQL write.** Three Phase 1a
   iterations were lost to wrong column names: `cum_date` (actual
   `game_date`), `home_score` (actual `actual_home_runs`),
   `median_price_over` (actual `median_away_price`). The Phase 0
   diagnostic schema-checked the upstream tables but not the
   downstream substrate. Future diagnostics should cover both.

4. **"Average SP" is a population definition, not a betting filter.**
   Cell membership emerges from filter computation, not team
   identity. Framings that import team-level risk concepts ("watch
   out for these teams") into a matchup-driven filter are categorical
   errors and were corrected during the session.

## Implementation artifacts

Pre-registration documents (locked, immutable historical record):
- `AVG_SP_LINEUP_PREREG_001_v1_0.md`
- `AVG_SP_LINEUP_PREREG_001_v1_1_amendment.md`

Phase 0 prerequisites:
- `diag_avg_sp_lineup_phase0.py` — substrate diagnostic
- `build_platoon_join.py` — PIT platoon utility
- `build_whiff_pit.py` — PIT whiff utility
- `verify_whiff_pit.py` — independent PIT verifier

Phase 1a execution:
- `study_avg_sp_lineup_phase1a.py` — 144-cell sweep
- Tables: `study_avg_sp_lineup_phase1a_results`,
  `study_avg_sp_lineup_phase1a_baselines`

Holdout and descriptive analysis:
- `holdout_test_2025.py` — frozen-threshold holdout test
- `descriptive_avg_sp_lineup_cell.py` — mechanism analysis

Database changes: 4 new tables persisted, no production tables
modified, no production scripts modified.

## References

- `RULES_FOR_CLAUDE.py` — Rule P3 (validated filters are binding),
  general red-team and pre-reg discipline rules.
- `DECISIONS.py` — "SESSION 25 — AVG_SP × LINEUP STUDY" full verdict
  with principles added.
- `HISTORY.py` — "PHASE 15: AVG_SP × LINEUP STUDY [Session 26]"
  build log.
- `ROADMAP.py` — "REMAINING WORK UPDATE (April 26, 2026 — Session 26)"
  forward-test substrate gap action items.
- `DEPENDENCIES.py` — RESEARCH UTILITIES section documenting all
  new scripts and tables.
- `ADR-027` — Phase A v1.1 rejection (precedent for clean
  pre-reg-driven rejection without softening).

# ADR-037: Phase 1.8 — Retail-vs-Pinnacle Gap by Year, Closure

**Status:** Accepted
**Date:** 2026-05-25 (Session 38)
**Pre-registration:** PHASE_1_8_PREREG_001 v1.0 + v1.1 + v1.2 (read together)
**Pattern follows:** ADR-027 (Phase A v1.1 rejection)

## Context

Session 37 (ADR-035) confirmed that UNDER_VALIDATED and HIGH_PARK_GAP
backtest claims are real on `historical_odds` (retail-driven) substrate
but FAIL across all 4 years on `pinnacle_historical_odds` (sharp-driven)
substrate. The validated edges beat retail mispricing, not sharp lines.

The structural question Session 37 left open: has the retail-vs-sharp
closing-line gap shrunk over time, such that the validated edges are
operating against a vanishing target?

Phase 1.8 pre-registered four hypotheses against this question:
- H1 (verdict): slate-wide |gap| compression
- H2 (verdict): directional asymmetry stability
- H3 (descriptive): UV-conditional signed gap
- H4 (verdict): HPG-conditional signed gap

The pre-reg went through two pre-execution amendments (v1.1: 2026 out of
scope due to substrate gaps; v1.2: UV definition locked to v5a full-band,
retail anchor locked to DK-only). All amendments surfaced through
substrate diagnostics before any hypothesis-relevant data was touched.

## Decision

Phase 1.8 closes with verdicts (H1 REJECTED, H2 ACCEPTED, H4 INDETERMINATE)
falling into pre-registered Section 7 outcome (C) — partial. The
validated filters remain live. Drawdown investigation must look elsewhere.

### Decision rationale by hypothesis

**H1 (slate-wide |gap| compression): REJECTED.**

Year-by-year mean |dk_close - pin_close|:
- 2023: 0.398 runs (n=1,924, 95% CI [0.380, 0.416])
- 2024: 0.359 runs (n=1,569, 95% CI [0.340, 0.378])
- 2025: 0.333 runs (n=1,693, 95% CI [0.312, 0.356])
- 2023-24 pooled: 0.380 runs (n=3,493, 95% CI [0.367, 0.393])

2025 vs 2023-24 pooled delta: -0.047 runs. Within the ±0.10 reject band.

There is a directional shrinkage trend across years (0.40 → 0.36 → 0.33)
but the magnitude does not meet the pre-registered 0.20 acceptance
threshold. Per pre-reg, H1 REJECTED.

**H2 (directional asymmetry stability): ACCEPTED.**

Pct(DK > Pinnacle) by year:
- 2023: 27.7%
- 2024: 34.7%
- 2025: 29.4%
- 2023-24 pooled: 30.8%
- 2025 vs 23-24 delta: -1.45pp (within ±5pp band)

DK closes BELOW Pinnacle on ~70% of games across all years. This is the
structural retail-vs-sharp directional asymmetry that the validated UNDER
edges exploit. It has not flipped.

**H3 (UV-conditional signed gap): DESCRIPTIVE ONLY (no verdict).**

UV-conditional mean(dk_close - pin_close) by year:
- 2023: +0.242 (n=252, 95% CI [+0.18, +0.30])
- 2024: +0.211 (n=237, 95% CI [+0.15, +0.27])
- 2025: +0.150 (n=327, 95% CI [+0.10, +0.20])

2025 CI does NOT overlap the 2023 CI. Point estimate compressed by ~38%
from 2023 to 2025. Per pre-reg v1.1 Amendment 3, H3 is descriptive-only
because its original motivation was a 2026-vs-prior comparison that was
removed from scope. No verdict issued; no action commitment from H3
alone.

This descriptive finding is documented for potential future pre-reg
motivation but does NOT drive action in Phase 1.8.

**H4 (HPG-conditional signed gap): INDETERMINATE.**

HPG sample sizes were thin as anticipated by the pre-reg:
- 2023: n=19, mean -0.45 (CI wide)
- 2024: n=26, mean -0.15
- 2025: n=12, mean -0.25

CIs overlap between 2025 and 2023-24 pooled. Per pre-reg CI-overlap rule,
verdict is INDETERMINATE regardless of point estimate.

The pre-reg correctly anticipated this: HPG volume is structurally low
(~7 bets/month). Under-power at n=12 in 2025 is sample-driven, not
methodologically remediable within Phase 1.8 scope. Per pre-reg, do NOT
extend window.

### Outcome matrix application

Verdicts (H1 REJECTED, H4 REJECTED/INDETERMINATE) fall into pre-registered
Section 7 outcome (C):

> "No compression detected at any level. Drawdown is NOT explained by
> retail-vs-sharp gap shrinkage. Action: drawdown investigation must look
> elsewhere. Validated filters STAY LIVE pending alternative explanation."

This action commitment is binding.

## Consequences

### Accepted

- UNDER_VALIDATED and HIGH_PARK_GAP remain in current operational status
  (live publishing per existing rules).
- The drawdown root cause is NOT slate-wide retail-vs-sharp gap
  compression. Adds to the list of rejected/retracted hypotheses
  established Sessions 34-37.
- The structural retail-vs-sharp directional asymmetry (DK closes below
  Pinnacle on ~70% of games) is empirically confirmed across 3 years and
  is the substrate the UNDER edges exploit.

### Forbidden (per pre-reg Section 8 rejection commitment, binding)

- No retesting of H1, H2, H4 in Phase 1.8 under any modification.
- No threshold relaxation (0.20 -> 0.15, 5pp -> 7pp, etc.) to rescue
  the rejected hypotheses.
- No window extension (180min -> 360min) to recover power.
- No book-mix relaxation (DK-only -> DK-with-fallback) to recover sample.
- No reframing H3's descriptive finding as a verdict-bearing result.
- Any further retail-vs-sharp work requires a new pre-reg
  (PHASE_1_8_PREREG_002 or PHASE_1_9_PREREG_001) with independent
  motivation, not response to this rejection.

### Open methodology finding

The H3 descriptive evidence (UV-conditional gap compressed from +0.24 to
+0.15 with non-overlapping CIs) is the most empirically informative
result in Phase 1.8 but carries no formal verdict because the pre-reg
correctly de-scoped H3 to descriptive-only when 2026 was removed from
the year scope.

This is a methodology lesson: pre-reg scope changes can strand
informative hypotheses without verdict authority. Future pre-regs that
descope hypotheses should consider whether to retain verdict-bearing
status with adjusted year scope, rather than dropping to descriptive-only.

The temptation to override the H1 REJECTED verdict with the H3
descriptive finding is exactly the Filter-A contamination pattern the
pre-reg is designed to prevent. The pre-reg is honored as written.

### Drawdown investigation status

Phase 1.8 closure adds to the list of rejected/retracted drawdown
hypotheses established Sessions 34-37. Status of all proposed root causes:

- "wRC+ train/serve divergence"               REJECTED (Session 34)
- "v3 vs v2 totals model swap"                REJECTED (Session 34)
- "26 missing veterans in pitcher_cumulative" REJECTED (Session 34)
- "K calibration broken at high edge"         RETRACTED (Session 35)
- "Stale K substrate"                         TOO SMALL (Session 35)
- "Lineup composite dead-code"                REJECTED (Session 36, ADR-034)
- "Books got sharper in 2026"                 REJECTED (Session 37)
- "Model regime change 2026"                  REJECTED (Session 37)
- "Pitcher cumulative v1->v2 drift"           REJECTED (Session 37)
- "Predictor rebuild is right scope"          REJECTED (Session 37)
- "Slate-wide retail-vs-sharp compression"    REJECTED (Session 38, this ADR)
- "HPG-conditional gap compression"           INDETERMINATE (this ADR)

Remaining candidate hypotheses requiring fresh pre-reg motivation:
- 2026 mid-season substrate shift on outcome side (run-scoring environment)
- Selection-bias mechanism on a non-pricing dimension
- The H3 descriptive finding (UV-conditional gap compression) as a
  pre-registered Phase 1.9 hypothesis with 2026 included after the daily
  pull patch and snapshot_slot reconciliation land

## Verification

### Pre-execution

- Substrate check (`diag_phase_1_8_substrate_check.py`) PASSed for
  prereg_version 1.2 before execute ran.
- Two diagnostic probes (DK extraction, DK year-concentration) surfaced
  v1.2 amendments BEFORE execute. No hypothesis-relevant aggregates
  touched until pre-reg was fully locked.

### Execution audit trail

- `phase_1_8_results` table: per-year and pooled metrics for H1, H2, H3,
  H4 with bootstrap 95% CIs.
- `phase_1_8_drops` table: per-year drop counts by reason. Drops
  acknowledged in this ADR (332/271/259 missing_pinnacle; 189/557/455
  missing_dk_relative_to_pinnacle). No drop pattern concentrates enough
  to invalidate.
- `phase_1_8_substrate_audit` table: v1.0, v1.1, v1.2 substrate-check
  rows preserved as forensic record.

### Bootstrap reproducibility

- random.seed(42) in execute script
- 10,000 iterations per CI
- Re-run produces identical CIs

## Follow-ups (not blocking)

- Phase 1.9 candidate: pre-register UV-conditional gap compression as a
  verdict-bearing hypothesis once 2026 substrate (daily pull patch +
  snapshot_slot reconciliation per Session 37 priorities #2, #3) is in
  place. Independent motivation: H3 descriptive finding of ~38%
  compression with non-overlapping CIs is empirically interesting and
  warrants verdict-bearing pre-reg with appropriate year scope.

- Drawdown investigation: next candidate angle requires its own pre-reg.
  No carry-forward of Phase 1.8 results as motivation; the rejection
  commitment forbids that.

- Hygiene items from Session 37 remain on roadmap, unchanged in priority
  by Phase 1.8 closure:
  - Daily pull patch (priority #2)
  - Snapshot_slot naming reconciliation (priority #3)
  - 227 specialty rows in 2026 pinnacle main table (priority #4)
  - Baseline-staleness patch in 11_predict_totals.py (priority #5)

## References

- PHASE_1_8_PREREG_001 v1.0 (locked 2026-05-25)
- PHASE_1_8_PREREG_001 v1.1 amendment (locked 2026-05-25, 2026 scope)
- PHASE_1_8_PREREG_001 v1.2 amendment (locked 2026-05-25, UV+DK defs)
- ADR-027 (Phase A v1.1 rejection — direct precedent pattern)
- ADR-029 (UV filter definition, v5a full-band reference)
- ADR-035 (Session 37 retail-vs-sharp structural finding)
- DECISIONS.py Session 37 D1-D6
- ROADMAP.py Session 37 priorities #1-#6
- phase_1_8_results, phase_1_8_drops, phase_1_8_substrate_audit tables
- diag_phase_1_8_substrate_check.py, diag_phase_1_8_dk_extraction_probe.py,
  diag_phase_1_8_dk_year_concentration.py, phase_1_8_execute.py

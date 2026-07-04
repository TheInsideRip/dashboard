# ADR-044: OUTS_UNDER demotes on corrected (v2) substrate — edge was largely contamination

Status: Accepted
Date: 2026-06-07
Session: 45
Pre-reg: PHASE_3_OUTS_PREREG_001.py (LOCKED v2.0)
Backtest: backtest_outs_v2_prereg.py (read-only; backtest_outs_v2_results.txt)
Extends: ADR-028 (06a relief-drop), ADR-033 (03c starter row-order),
         ADR-043 (v2 not wired / live contamination)
Closes: ADR-033 Phase 3 re-validation for the OUTS family.
        (K props remain a SEPARATE later pre-reg — NOT closed here.)

## Context

OUTS_UNDER_STRONG (claimed 58.0% WR) and OUTS_UNDER_ELITE (claimed 64.5% WR)
have been on hold since Session 32, pending re-validation against the corrected
v2 bullpen substrate (ADR-033). v2 was rebuilt and verified clean in Session 44.
PHASE_3_OUTS_PREREG_001.py asks the one question that governs cutover:

  Does OUTS_UNDER survive on corrected v2 substrate, with P20 re-derived on v2?
  (Question A. Whether the v1 number was itself a bug artifact is Question B,
  diagnostic only, explicitly out of scope.)

### Method note — pre-reg amended v1.1 -> v2.0 (pre-execution, gate-forced)

The v1.1 outcome reconstruction was event-counting (counting out-events on the
starter's pitches). It failed its own 95% outcome-validation gate at 77.1% vs
2026 booked outs, because base-running outs (caught stealing, pickoff) are
absent from `pitches_historical.events` and never advance a PA-ending event —
a structural ~78% ceiling, proven (not guessed) in Session 44 via a mod-3 test
and a validated innings-based prototype.

The pre-reg was amended to v2.0: reconstruction changed to INNINGS-BASED
out-state progression (out-state delta per half-inning, terminal PA completes
at 3, attribution to the last-pitch pitcher, summed for the chronological-first
starter; method per `prototype_outs_innings_recon.py`). This is a PRE-EXECUTION
amendment: no win-rate, ROI, or hypothesis aggregate was EVER computed under
v1.1 — the gate aborted before any aggregate. All filters (H1/H2, E1-E4,
G1-G3, two-tier G2, decision rule, assumed -120, 2024-25 window, both arms)
were frozen before any WR was seen. The innings method RE-CLEARED the outcome
gate on the real run at 98.5% (not inherited from the prototype); the delta
distribution showed no structured negative band, confirming the
starter/reliever attribution boundary ported correctly.

## Finding

On corrected v2 substrate, BOTH OUTS_UNDER hypotheses DEMOTE.

| hyp (outs_line) | arm | n   | P20 | WR    | ROI@-120 | 2024 / 2025   | G2 monthly  | decision        |
|-----------------|-----|-----|-----|-------|----------|---------------|-------------|-----------------|
| STRONG >=17.5   | v1  | 726 | 255 | 53.6% | -1.8%    | 54.8% / 52.4% | 11/14 (79%) | DEMOTE (1/3)    |
| STRONG >=17.5   | v2  | 714 | 110 | 52.1% | -4.5%    | 51.8% / 52.4% | 8/14 (57%)  | DEMOTE (0/3)    |
| ELITE >=18.5    | v1  | 138 | 259 | 63.0% | +15.6%   | 69.2% / 55.0% | 9/12 (75%)  | RE-VALIDATED 3/3|
| ELITE >=18.5    | v2  | 142 | 112 | 56.3% | +3.3%    | 60.2% / 50.0% | 6/12 (50%)  | DEMOTE (1/3)    |

> **Gate-count note:** counts above use the TRUE -120 breakeven (G3 passes iff WR > 54.55%). The original `backtest_outs_v2_prereg.py` used a lenient G3 threshold of 0.4545 (100/220, a code quirk), under which STRONG showed v1 2/3 and v2 1/3; corrected here. Verdicts are unchanged — both STRONG arms DEMOTE at <=1 gate either way, and ELITE is unaffected (its WRs sit far from the threshold).

The edge that looked strong on v1 was substantially a contamination artifact:

- ELITE reads RE-VALIDATED 3/3 (63.0%) on v1 but DEMOTE 1/3 (56.3%) on v2 — a
  -6.7pt drop, monthly stability collapsing 75% -> 50%, and 2025 falling to a
  coin flip (50.0%).
- STRONG was only HOLD on v1 and DEMOTE on v2 (52.1%, below the -120 breakeven
  of 54.55%).
- Mechanism is visible in P20: the freshness cutoff is ~255-259 on v1 vs
  ~110-112 on v2. The v2 P20 (110) matches the 03c_v2 rebuild exactly. The v1
  "fresh bullpen" filter was keying off the ~2x-inflated metric (ADR-033), so
  it was selecting a different — and not genuinely edge-bearing — universe.

This is exactly the trap ADR-043 flagged: a "RE-VALIDATED" line computed on
contaminated v1 substrate is not actionable.

## Decision

OUTS_UNDER_STRONG and OUTS_UNDER_ELITE are DEMOTED. Both are marked
bug-dependent: the v1 numbers did not survive substrate correction. Neither is
eligible to publish. The Session-32 hold is resolved as DEMOTE (not lifted).

## Caveats (per locked pre-reg)

- ROI uses an ASSUMED -120 price (no booked outs price column exists). ROI is
  illustrative; WR is primary and price-independent.
- Window is 2024-2025 (the `historical_k_props.outs_line` coverage bound). No
  2023, no 2026.
- The historical 58% / 64.5% v1 claims were NOT reproduced (muddy P20
  provenance). This test established a clean-procedure v1 baseline and a v2
  result under one identical procedure; the v1 arm here is that baseline, not
  the legacy claim.

## Scope / non-actions

- No serving-code cutover this session. Cutover remains a later gated step and
  depends on the K-prop re-validation too (separate pre-reg).
- E2 (06a_v2/03c_v2 starter divergence) exclusion was applied as locked; its
  builder-fidelity was not re-litigated (frozen filter).
- Artifacts retained: prototype_outs_innings_recon.py,
  _bak_prebuild_20260607_133238 tables, verify_06a_v2_stepwise.py,
  check_substrate_state.py, check_outs_line_coverage.py.

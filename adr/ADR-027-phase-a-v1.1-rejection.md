# ADR-027: Phase A v1.1 Pinnacle vs DraftKings Totals — Full Rejection

**Status:** Accepted
**Date:** 2026-04-24 (Session 25)
**Pre-registration:** PHASE_A_PREREG_001 v1.1

## Context

Phase A was the first pre-registered analysis using `pinnacle_historical_odds`,
the sharp-book anchor built in Session 21 (249,182 rows, 2023-2025 regular
seasons, 12 snapshots per game-date). The hypothesis space: whether static
or dynamic line-disagreement between Pinnacle (sharp) and DraftKings (public
anchor) produces a profitable edge on MLB totals at DK actual prices.

Four hypotheses were locked in PHASE_A_PREREG_001 v1.1:

- **H1**: Pinnacle closes ≥0.5 runs below DK → bet DK under
- **H2**: Pinnacle closes ≥0.5 runs above DK → bet DK over
- **H3** (two sub-tests): Pinnacle's internal open-to-close movement predicts direction
- **H4** (two sub-tests): Reverse line movement — Pinnacle moves opposite to its final gap with DK

Sample contract: 5,617 MLB regular-season games across 2023-2025, after
coverage gates (open ≥6 hr pre-game, close ≤180 min pre-game), joined to
historical_odds for DK extraction and game_totals_backtest for outcomes.

## Decision

All four hypotheses REJECTED. Phase A v1.1 closes with no edges promoted to
production.

### Decision rationale by hypothesis

**H1 (PIN_UNDER_TO_DK):** PROMOTED at Phase 1a with ROI +4.74%, WR 55.66%,
all 3 years positive (2023 +5.18%, 2024 +7.58%, 2025 +1.07%). Failed G5
(recent decay) preview: last 6 months (2025 Apr-Sep) ROI +0.71%, below
threshold of +2.37% (50% of overall ROI). The 2025-only metric of +1.07%
was already a warning; the last-6-months window showed the signal is
actively decaying. Per pre-reg, REJECT.

**H2 (PIN_OVER_TO_DK):** REJECTED at Phase 1a. Pooled ROI +1.43% falls
below +2.00% gate. Year-split sign flip confirmed: 2023 +6.33%, 2024
-2.26%, 2025 -3.24%. Signal was present in 2023 and dissipated in
subsequent years.

**H3 (composite):** REJECTED. Both sub-tests failed Phase 1a: H3a
(pin_move ≤ -0.5 → under) at +0.95%, H3b (pin_move ≥ +0.5 → over)
at -0.27%. Per pre-reg composite rule, H3 fails if either sub-test fails.

**H4 (composite):** REJECTED. H4a (RLM_UNDER) promoted at Phase 1a with
+4.31% ROI but failed G5 preview (last 6 months +1.54%, threshold +2.16%).
H4a's profile tracks H1 closely because RLM_UNDER is a strict subset of H1
(it requires `delta_close ≤ -0.5` plus additional `pin_move ≤ -0.5`).
H4b (RLM_OVER) failed Phase 1a at +1.90% below +3.00% gate. Per pre-reg
composite rule, H4 fails.

### Structural finding: 2023-2024 sharp signal existed; 2025 arbitraged

The pattern observed across multiple hypotheses is consistent:

- 2024 was the peak year for every hypothesis tested, whether promoted or rejected
- 2023 showed moderate positive signal on "under" direction hypotheses
- 2025 showed material decay or reversal across most hypotheses

Specifically for H1:

| Year | n | WR | ROI |
|---|---|---|---|
| 2023 | 603 | 55.73% | +5.18% |
| 2024 | 640 | 57.14% | +7.58% |
| 2025 | 566 | 53.93% | +1.07% |

The 6.5-point ROI gap between 2024 and 2025 on the same filter with
comparable n is not noise — it's evidence of market participants actively
incorporating Pinnacle-vs-DK disagreement into their pricing.

**This decay is not itself an edge.** We cannot trade past divergence that
no longer exists. But it's a useful methodological finding: any sharp-vs-public
totals edge claim that does not demonstrate 2025 persistence should be
scrutinized as likely historical rather than current.

### G7 (Filter-A baseline) result — separately notable

Preview of G7 showed the parent population (bet DK under blind on all 5,617
Phase A games) produced -1.66% ROI. H1's filter added +6.40pp of real lift
over parent (-1.66% → +4.74%). This means H1's filter did real work —
the edge wasn't a selection-bias artifact of the Phase A sample itself.
G7 passed cleanly. The killer was G5 (temporal decay), not G7
(baseline contamination). This is a different failure mode from
RL_PREREG_001 H5, which failed G7.

## Consequences

### Accepted

- No new production taggers deployed from Phase A v1.1
- `phase_a_results` table retains both Phase 1a and Phase 1a-final rows
  for forensic traceability
- `pinnacle_historical_odds` infrastructure remains in place and is
  available for future pre-registered hypotheses

### Forbidden (per pre-reg REJECTION COMMITMENT)

- No retesting of H1-H4 in Phase A v1.1 under any modification
- No Filter-A contamination: no tweaking time windows, price buckets,
  or filter thresholds to rescue the rejected hypotheses
- Any future Pinnacle-vs-DK hypothesis must be registered in
  PHASE_A_PREREG_002 (or later) with distinct motivation and filter criteria
  independent of what we learned here

### Open methodology improvements identified

- **Duplicate handling in historical_odds**: 47 events had 2+ rows per
  (game_date, home_team_full, away_team_full) combination. `ROW_NUMBER()
  OVER ... ORDER BY snapshot_time DESC` dedup caught 57 of 98 duplicates.
  Remaining 41 duplicates suggest either identical-snapshot-time collisions
  or dedup key incompleteness. Not fatal (metrics shifted <0.05pp) but
  worth a dedicated fix before next Phase A pre-reg
- **G5 preview as a Phase 1a red-team pattern**: previewing decay before
  committing to full Phase 3 verification saved substantial work. This
  pattern should be standardized — any Phase 1a-promoted hypothesis gets
  a quick G5 preview before Phase 3 gets built

### Lessons honored

This rejection honors the strict pre-registration discipline established
in RL_PREREG_001. The temptation to redefine G5's "last 6 months" to
exclude August 2025, or to redefine the filter to match only 2024-strong
months, is exactly the Filter-A contamination pattern the pre-reg is
designed to prevent. Both H1 and H4a stay rejected, with documentation
of the structural 2024-peak finding preserved here for future reference.

## References

- PHASE_A_PREREG_001 v1.1 (this repo, locked 2026-04-24)
- phase_a_results table (8 rows prereg_version='1.1', 8 rows '1.1_final')
- Session 25 diagnostic chain: diag_phase_a_preflight v1-v6, v3 outcome source,
  red team + G5 preview
- RL_PREREG_001 v1.1 (the pattern this follows)
- ADR-023, ADR-025, ADR-026 (the ADR pattern this extends)

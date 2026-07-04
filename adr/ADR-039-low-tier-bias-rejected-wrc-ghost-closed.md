# ADR-039: Session 39 Closeouts — Low-Tier Bias REJECTED, wRC+ Train/Serve Divergence Closed as Ghost

**Status:** Accepted
**Date:** 2026-05-28 (Session 39 verdicts; recorded in narrative docs 2026-05-31)
**Pre-registrations:** PHASE_2_0_PREREG_001.py v1.0 (low-tier bias)
**Related:** ADR-034 (lineup composite + low-tier carry-forward), ADR-037
             (Phase 1.8 closure + drawdown root-cause list), ADR-038
             (Phase 1.9a INDETERMINATE)

## Context

The narrative docs (ROADMAP/DECISIONS/HISTORY) stopped at Session 38. Two
Session 39 verdicts existed only in result tables, locked pre-regs, and
ADR-038, and are recorded here. Both bear on the still-unexplained 2026
totals drawdown.

## Verdict 1 — Phase 2.0a: low-tier predicted-total bias REJECTED

**Pre-registration:** PHASE_2_0_PREREG_001.py, v1.0 LOCKED 2026-05-28. The
lock was applied to the `# Version:` line by
patch_lock_phase_1_9_and_2_0_preregs.py (the project's canonical lock
signal per the file's own L16). The separate `# Status: DRAFT` line (L12)
is a stale residual the lock patch did not rewrite; it does not negate the
lock.

**Substrate / definitions (locked):** game_totals_backtest, seasons
2023-2025, cumulative-both starters; signed_bias = actual_total −
predicted_total; tier boundaries locked to ADR-034 (low tier =
7.5 < predicted_total ≤ 8.5).

**Result** (phase_2_0a_results, run_ts 2026-05-28T20:20:30Z):

| Hypothesis | Bucket | Value | 95% CI | n | Verdict |
|---|---|---|---|---|---|
| H1 (structural non-zero low-tier bias) | pooled_low_2023_2025 | +0.0387 | [−0.1428, +0.2208] | 1990 | **REJECTED** (CI crosses zero) |
| H2 (tier specificity) | — | — | — | — | N/A (gated on H1) |
| H3 (direction persistence) | — | — | — | — | N/A (gated on H1) |

**Conclusion:** ADR-034's −0.83 low-tier miss (148-game, 30-day 2026
window, low-tier n=56) does NOT reproduce as a structural miss across three
years. It is a **2026-specific reading**, not a structural calibration
defect. Per the locked outcome matrix (B), no historical-recalibration
project is justified; any real problem is 2026-specific (drift / regime /
sampling) and would need its own pre-reg to pursue.

## Verdict 2 — wRC+ train/serve divergence: REJECTED as a ghost finding

Re-derived from **current code only** (read-only; no DB, no aggregate). The
totals model is a deterministic log5 formula, not a fitted model: "train" =
the backtest substrate builder (10a_game_totals_model.py); "serve" =
11_predict_totals.py.

- **Serve (11_predict_totals.py):** wRC+ appears exactly once — the L261
  docstring "Uses raw platoon wOBA (not wRC+) to avoid park factor
  double-counting." It is not loaded, assigned, or used. The offense input
  is team_offense off_woba_vsL / off_woba_vsR (L270-285).
- **Train (10a_game_totals_model.py):** wrc_plus is built (L152-190) and
  passed into predict_game_runs (L654); away_wrc / home_wrc are assigned
  (L409-410) but **never consumed** — the run computation uses off_woba,
  pitcher_xwoba, bp_xwoba, and the park factor. Comment L488-489: "wRC+ is
  not used in v2 matchup formula." Header L7-8, L17 document the deliberate
  v1→v2 removal (v1 "double-parked" wRC+).

**Finding:** there is **no live wRC+ feature on either path**, so a
train/serve divergence on wRC+ is not possible.

**Cross-ADR contradiction resolved:** ADR-037's statement ("wRC+ is NOT in
11_predict_totals.py") is correct. ADR-034's "train/serve divergence on
wRC+ … remains open" and ADR-038's "deferred train/serve divergence (wRC+)"
framings are **CLOSED** by this code re-derivation. One nuance ADR-037
omitted: wRC+ is not entirely absent from the train-side *file* — it
survives as dead-but-assigned code in 10a (vestigial from v1) — it simply
never enters the prediction.

**Caveats:** the identical dead-assignment in
10a_v2_substrate_for_phase3.py (L443-444) was confirmed via grep (no use
after assignment), not a full read. Downstream consumers of
game_totals_backtest were not exhaustively traced.

## Drawdown investigation status

**PAUSED pending data — not permanently closed.**

- Known testable leads are exhausted: low-tier bias REJECTED (this ADR);
  wRC+ divergence CLOSED as ghost (this ADR).
- Cause count: low-tier bias is the one genuinely new rejection this
  session, taking the tally from 12 (Sessions 34-38, per ADR-037) to 13.
  wRC+ was already one of those 12; it is only firmly closed here (code
  re-derivation) and adds nothing to the count.
- The **only live hypothesis** is UV-conditional retail-vs-sharp gap
  compression → Phase 1.9b (PHASE_1_9_PREREG_001 v1.1; reference CI locked
  in phase_1_9a_results per ADR-038). It is **BLOCKED** pending 2026
  forward-collected clean UV-high substrate (cumulative-both SP, gap in
  [−1.0, −0.25]); Phase 0 full-slate retail persistence is not yet built,
  and the 1.9b gate requires n ≥ 120 clean 2026 UV games.
- Drawdown remains ~10u below peak, empirically real, unexplained. No new
  angle without fresh pre-reg motivation (Section 8 rejection commitments
  binding).

## Consequences

- No publish-rule change from either verdict. Validated filters stay per
  existing ADRs (029/032/033, reaffirmed Session 38).
- Documentation only: this ADR plus Session 39 entries in
  ROADMAP/DECISIONS/HISTORY. No analysis code or database modified.

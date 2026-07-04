# ADR-048 (Accepted): K-prop drawdown (−63.18u) is NOT a fixable substrate defect — H_NULL, K stays dark

Status: **Accepted** (promoted from DRAFT 2026-06-13) — pre-registered investigation (`PHASE_K1_PREREG_001.py`,
locked 2026-06-12) per `claude_code_prompt_kprop_drift_FINAL.md`. READ-ONLY; no
serving/builder/tagging code changed. Outcome **H_NULL** (pre-authorized: "K stays dark").
Relates to: ADR-032 (season-hardcode), ADR-045 (v2 cutover), ADR-047 (frozen-v2 fix),
ADR-035/041 (overconfident-selection / prop CLV INDETERMINATE), and the
prediction-bias-gate finding (pooled live bias = selection artifact).

> All figures verified first-hand, read-only, 2026-06-12. Tagged verified vs inferred.

## S0-PRE — the metric is REAL (verified)
Independent recompute from `bet_tracker` raw (predicted_k & result_k in ONE row — no join,
no cross-join inflation possible): **bias −0.320, MAE 1.930, −63.18u, WR 0.487, n=948** —
exact match to the reported numbers. Not a reporting artifact. (Rules out the ADR-032/036
tracker-bug class.)

## Mandatory first step — regime decomposition (boundaries derived from records)
Regimes from HISTORY/ADRs/serving-script `.bak` timestamps (NOT the brief's "~06-06"):

| Regime | dates | substrate state | n | bias | MAE | **P&L** | WR |
|---|---|---|---|---|---|---|---|
| R1 | 03-29→05-09 | v1, ADR-032 hardcode active (reads 2025) | 491 | −0.299 | 1.963 | **−11.02u** | .508 |
| R2 | 05-10→05-16 | + TTO change, hardcode still active | 98 | −0.473 | 1.951 | **−24.96u** | .388 |
| R3 | 05-17→06-06 | post-ADR-032 fix, **CLEAN v1** | 298 | −0.346 | 1.908 | **−22.80u** | .487 |
| R4 | 06-07→06-11 | v2 cutover, frozen-06-06 (ADR-047 defect) | 61 | −0.113 | 1.733 | **−4.41u** | .475 |

**Headline (verified): the loss is NOT in the just-fixed v2 window.** R4 (the frozen-v2
known-defect) contributed only **−4.41u (~7%)**. The drawdown decomposes into: the now-FIXED
ADR-032 hardcode bleed (R2, −24.96u over one week — the documented +15→−15 DD), the now-FIXED
v2-frozen window (R4, −4.41u), and **−33.8u across R1+R3 including −22.80u on fully CLEAN v1
substrate (R3).** The model loses on clean substrate — so the drawdown is not a fixable
substrate bug. Today's ADR-047 v2 fix is NOT a drawdown fix (the brief's warning, confirmed).

## S0a / S0-PRE-2 — accuracy is fine; the bias "sign-flip" is invalid
- **S0a:** live MAE 1.930 vs backtest 1.864 = +0.07 = **1.4 SE — INSIDE the noise band.**
  Point accuracy is NOT degraded vs backtest. Per the prereg this marks H1/H2/H3 LOW priority.
- **S0-PRE-2:** backtest +0.145 / 1.864 (k_prop_backtest n=11,286) is a **full-slate per-start
  reconstruction**; live −0.320 is the **selection-biased bet universe**. Different populations
  → the "−0.32 vs +0.15 sign-flip" is **INVALID** as like-for-like; dropped. (Confirms the
  prior prediction-bias-gate verdict.)

## Direction decomposition — the real signature (overconfident selection, not substrate)
OVER bets over-predict in EVERY regime (bias +0.68…+0.96; total **−41.45u**); UNDER bets
under-predict (bias −0.68…−1.34; total **−21.74u**). The model's *extreme* predictions are too
extreme; the edge filter selects exactly those miscalibrated tails. This **persists on clean
R3** → a calibration/selection property of the model, not a data defect. Same signature as
ADR-035/Session-41 totals overconfidence. The pooled −0.32 is the net of opposite-sign
direction biases — a pooling artifact, not a single phenomenon.

## H1–H4 verdicts
- **H1 (event-vocab drift) — CLEAN (verified):** no new 2026 K-events; `K_EVENTS` captures all
  `strikeout*`. Unclassified descriptions (`automatic_strike`, `foul_bunt`, `bunt_foul_tip`)
  hit only secondary CSW/whiff denominators negligibly and aren't new. No silent miscount.
- **H2 (order-dependent) / H3 (train/serve) — LOW PRIORITY / NOT-RUN:** S0a (MAE in band)
  deprioritizes them; today's v2 rebuild validated cleanly (stable sort, 0 rows v2<v1); MAE
  parity with backtest leaves no accuracy gap for them to explain. Red-team note (ADR-039):
  any 2026 feature difference is roster turnover, not a defect.
- **H4 (price/CLV) — LIMITED:** no stored 2026 K closing-line/price (G2), so closing-CLV is not
  computable; extends ADR-041's INDETERMINATE. Indirect read: the OVER-side over-prediction +
  tail miscalibration is a selection/calibration leak, not a measurable closing-line edge.
- **S0b:** loss is a MAY phenomenon (−50.44u of −63u); April (same hardcode substrate) was
  +2.60u → substrate doesn't explain the timing. The only step at a substrate boundary is the
  EXPECTED WR improvement at the 05-17 ADR-032 fix (already handled). No unaddressed step.
- **S0c:** selection mix stable across regimes (OVER% 36–41%, line ~5.0, edge 15–20%). No drift.

## Decision — H_NULL (K stays dark; closed)
Metric real; MAE in noise band; H1 clean; no substrate step; loss persists on clean substrate
and decomposes into two ALREADY-FIXED defects (ADR-032 hardcode R2, ADR-047 frozen-v2 R4,
together ~−29u) plus overconfident-selection/variance on clean substrate (R1+R3, ~−34u). There
is **no new fixable defect**. K props **stay dark**. No H_EDGE (H1/H2 found no correctable
miscount) → no forward-test tagger spec. Re-validation of K would require a calibration fix
(tail overconfidence) proven out-of-sample — a separate decision, not granted here.

## What this does NOT establish
Not that the model is worthless — its point MAE matches backtest. It establishes that the
edge-based BETTING selection is miscalibrated at the tails and unprofitable on clean substrate.
Not a closing-CLV verdict (no data). Not an attribution of the clean-substrate loss to skill
vs variance (n=298 in R3; could be partly variance — but it is not a fixable bug either way).

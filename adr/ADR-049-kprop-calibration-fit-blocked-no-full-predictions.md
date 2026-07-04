# ADR-049 (Accepted): K-prop calibration-fit question is unanswerable — full per-start predictions were never persisted (plumbing gap)

> **PLUMBING GAP CLOSED 2026-06-13:** `08::save_full_slate_k` now persists the full per-start K slate + inputs to `k_prop_full_slate` (UPSERT), resolved by `09e_k_full_slate_resolve.py` (actual_k/tbf/was_bet), wired into `resolve_morning.bat [1/8]`. Forward data accumulates from 2026-06-13; the calibration fit (`PHASE_K2_PREREG_001.py`) re-runs after weeks of clean forward data — a separate decision.

Status: **Accepted** (promoted from DRAFT 2026-06-13) — read-only measurement per
`claude_code_prompt_kprop_calibration_test.md` (pre-reg `PHASE_K2_PREREG_001.py`,
locked 2026-06-12). Outcome **INDETERMINATE, blocked at D1**. Does NOT reopen ADR-048
(H_NULL); this CONFIRMS it. No serving/recalibration/tagger/tracker change.
Relates to: ADR-048 (K H_NULL, tail-overconfidence), ADR-032/045/047 (regime
contamination), Session-42 totals_full_slate (the precedent fix).

> All claims verified first-hand, read-only, 2026-06-12.

## The question
ADR-048 found K miscalibration (overs over-predict, unders under-predict) that persists
on clean substrate. Narrow downstream question: is that miscalibration a **stable,
monotonic, out-of-sample-exploitable** function of the prediction, or noise? Answering it
requires fitting a calibration curve on the **full** per-start prediction set (D1) over the
**clean R3 window** (D2 = 2026-05-17→06-06).

## Blocking finding (D1) — full predictions are never stored (verified)
| Source | What it holds | Why it can't serve the fit |
|---|---|---|
| `07_predict_today.py` | a prediction for **every** starter | **print-only** — `main()` ends `print_predictions()`→`conn.close()`, no `to_sql`/`INSERT`/`CREATE`. Discarded. |
| `27i_k_prop_tagger.py` | — | only `UPDATE clv_tag` on existing `bet_tracker` rows |
| `08` (run_kprops) | — | saves only the **+3% actionable** subset to `bet_tracker` |
| `bet_tracker` | 2026 bet rows (pred_k + result_k) | the **+3%-edge-SELECTED** subset — fitting calibration on it re-introduces the exact selection bias under study (D1-forbidden, circular) |
| `k_prop_backtest` | full-slate per-start pred vs actual | **2023-25 backtest reconstruction — no 2026**, not the served predictions |
| `totals_full_slate` | full-slate totals | totals only; **no K equivalent exists** |

Quantified gap (R3, 2026-05-17→06-06): `07` produced **~560** starter predictions;
`bet_tracker` retained only **298** +3%-selected bet rows (~53% of starts, and biased toward
the model's extreme/high-edge predictions — i.e. the miscalibrated tails themselves). The
unbet ~47% have **no stored prediction**. The D1-clean fit set **does not exist**.

## Verdict
**INDETERMINATE — Decision-Bar item #1 (adequate clean full-prediction N) cannot even be
evaluated.** The remaining bars (within-R3 stability, out-of-sample monotonicity, short-outing
control, vig clearance) are moot without the data. This is NOT "no signal proven" and NOT
"signal" — it is **unanswerable with current plumbing**, which itself CONFIRMS ADR-048's
H_NULL (there is no clean basis on which a fixable edge could be demonstrated today).

Falling back to `bet_tracker` would manufacture a curve on the selected tails and is explicitly
refused (D1).

## Recommendation (a build task, not done here)
Persist **full per-start K predictions** going forward — a `k_prop_full_slate` table written
by `07_predict_today.py` (or `08` before the +3% gate), write-once per (game_date, pitcher_id),
storing predicted_k + its features + later-resolved actual_k + TBF/IP (for the D3 short-outing
control) + an input-provenance/source flag (to exclude fallback-input starts) — exactly the
pattern `totals_full_slate` already established for totals (Session 42). The clean window also
needs `actual_k` backfilled by a resolver (note: `totals_full_slate.actual_*` is currently left
NULL — the same resolver gap must be closed for K, or the table is inert like that one).

After ~several weeks of clean post-ADR-047 R-forward accumulation, re-run
`PHASE_K2_PREREG_001.py`'s locked method. Until then the calibration question stays open by
**absence of data**, not by evidence of a flat curve.

## What this establishes / does not
Establishes: the fittability question is **blocked by a data-plumbing gap**, not resolved.
Does not establish: that the miscalibration is or isn't exploitable — untestable now. Does not
change ADR-048. No code, serving, or tracker touched.

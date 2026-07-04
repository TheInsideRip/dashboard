# ADR-053 (Accepted): Whiff signal is additive to the K MODEL but dead as a BET; production whiff_vuln was REBUILT to the validated v2 this session

Status: **Accepted**. The signal facts (validated construction, additive-to-model, dead-as-bet)
are Accepted from this session's read-only studies. The production-build claim was RE-CONFIRMED
by direct inspection of the live files THIS RUN (2026-06-16): the earlier-campaign "broken build"
is now **RESOLVED** -- production was rebuilt to the validated v2 build today (see below).
Relates to: ADR-048 (K stays dark -- reinforced), ADR-052 (detection floor -- the bet test is not
a floor artifact), ADR-054 (last-start recency, the other dead K angle), ADR-035 (overconfident
selection).

> Signal statistics are attributed to their study outputs (2026-06-16). The production code/table
> state was verified first-hand this run (grep of live files + DB family-string check).

## Signal is real and additive to the K model (study facts)
The validated `whiff_idx` (4 pitch families FB/SL/CB/OFF including FC and FO; WHIFFS =
swinging_strike + swinging_strike_blocked + foul_tip; 50-pitch cell floor + handedness (stand x
family) prior fallback; strict as-of) is additive to the K model:
- Per diag_arsenal_additivity_20260615.py output (arsenal_additivity_OUT.txt, FRAME_A full
  controls C5, which INCLUDE predicted_ks and cum_whiff_rate): Poisson GLM LR coef +0.0849/SD,
  **LR p = 1.21e-82**, **IQR effect +0.547 Ks/start**, **VIF(whiff_idx) = 1.03**. A swap test
  (replacing cum_whiff_rate with whiff_idx) **improves log-likelihood by 149.74**.
- Per diag_arsenal_vs_lineup_20260615.py output (Step-5 gate, controls = pitcher K% + lineup K%):
  partial corr **+0.125** (this is the +0.125 figure; NOTE/discrepancy: the session summary
  attributed +0.125 to "controlling predicted_ks + cum_whiff_rate," but that control set is the
  additivity study's, whose own secondary partial is ~+0.19 and whose PRIMARY metric is the GLM
  LR test above, not Pearson). Both studies agree the signal carries merit beyond the rate stats
  the line already prices.

## Dead as a BET vs the K line at actual juice (study fact)
Per diag_whiff_vs_kline_recalibrated_20260616.py output (2026-06-16): at the recalibrated
breakeven-plus bar, the signal sorts Ks (tercile OVER-ROI gradient is monotone) but the best
bucket is sub-breakeven; the top/bottom-tercile strategy is **-3.0% ROI on the 2025 holdout,
negative in both 2025 halves**. Median juice OVER -110 (be 0.524) / UNDER -119 (be 0.543) is the
wall. Not bettable.

## Production build state -- RE-CONFIRMED THIS RUN (claim RESOLVED)
The earlier-campaign finding was that production `06b_whiff_profiles.py` / `whiff_vuln.py` were a
BROKEN build of the validated signal (3 families not 4, full-season not as-of, inconsistent
per-batter normalization, 100-pitch floor with no fallback). Direct inspection of the LIVE files
on 2026-06-16 shows this is **no longer true -- both were rebuilt to the validated v2 build today**:
- `06b_whiff_profiles.py` header: "v2 -- validated ... REBUILT 2026-06-16 to match the validated
  arsenal-vs-lineup study." FAMILY_MAP now has **4 families FB/SL/CB/OFF including FC and FO**;
  whiff/swing defs match the study; **50-pitch floor + handedness prior fallback**; optional
  `--asof` leakage-safe build; atomic _new->swap write.
- `whiff_vuln.py` header: "v2 -- validated build ... REBUILT 2026-06-16"; the v1 per-batter
  normalization bug (each batter normalized over a different denominator) is FIXED (every batter
  scored over the same fixed arsenal-weighted family set); expects 4-family strings.
- DEPLOYED: live `batter_whiff_profiles` (4,035 rows) and `pitcher_arsenal_profiles` (2,535 rows)
  now hold the 4-family strings {FB,SL,CB,OFF} (verified) -- the rebuild ran, not just the code.

## Display-only / non-gating -- CONFIRMED (picks are NOT corrupted)
The whiff/mismatch score remains **display-only and does NOT gate published picks**, confirmed in
the live taggers this run:
- `22l_tag_validated_edges.py`: total_mm feeds only an "MM: HIGH/LOW/MID" print label; the code
  comment states "DISPLAY-ONLY: gates/tiers/picks unaffected."
- `26e_mlrl_tagger.py`: `mm_diff` builds only an "MM: ... ADV" print string; pick selection
  (elite vs track) never references it.

## Disposition
Whiff is a K-MODEL feature improvement (now correctly built in production at the profile-table
level, but not yet wired as a model input/feature in the K predictor), not a standalone bet.
K stays dark (ADR-048).

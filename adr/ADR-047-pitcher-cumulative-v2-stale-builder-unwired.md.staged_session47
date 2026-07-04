# ADR-047: pitcher_cumulative_v2 was frozen at 2026-06-06 — v2 cumulative builder never wired into the daily chain (FIXED)

Status: **Accepted**
Date surfaced: 2026-06-12 (read-only investigation, ADR-047 DRAFT / gate-G2 abort)
Date fixed: 2026-06-12
Relates to: ADR-045 (v2 serving cutover 2026-06-07), ADR-046 §B (bullpen_workload_v2
zero-collapse — same class of defect), ADR-028 (the v2 relief-drop fix that 06a_v2 implements).

> All figures verified first-hand against the live repo/DB on 2026-06-12. Claims tagged
> verified-by-measurement vs inferred.

## Defect (verified)

ADR-045 (2026-06-07) cut K/totals/MLRL serving to the v2 substrate. The v2 **cumulative
pitcher** builder `06a_v2_cumulative_pitcher_metrics.py` was wired into **no** daily
pipeline (resolve_morning / pregame / 05d `PHASE2_RECALC_SCRIPTS` / 05e — exhaustive grep
incl. python-level subprocess invocation: only the **v1** `06a_cumulative_pitcher_metrics.py`
appears). So `pitcher_cumulative_v2` was frozen at its last manual build, **max game_date
2026-06-06**, while v1 `pitcher_cumulative` rebuilt daily (max 06-10). Every K/totals/MLRL
prediction and tag from 2026-06-07 onward read cumulative pitcher features frozen at 06-06.

This is the ADR-046 §B pattern (serving cut to v2, v2 builder unwired) on the cumulative
table instead of the bullpen table. It blocked the K-prop drift investigation at gate G2.

## Blast radius (verified read-only)

**Serving readers of `pitcher_cumulative_v2`:** `07_predict_today.py:89`,
`27i_k_prop_tagger.py:159` (K); `11_predict_totals.py:206` (totals);
`11b_predict_mlrl.py:347` (MLRL); `22l_tag_validated_edges.py:278` (`cum_games` CLV gate).
(`10a_v2_substrate_for_phase3.py` is a backtest builder, not daily serving.)

**Contamination window:** 2026-06-07 → 06-11 (cutover → last completed bet day).
- In-window tracked bets: **61** K (bet_tracker), **24** totals, **63** MLRL; **7** published_picks.
- **Magnitude — SMALL and bounded** (vs the corrected v2 baseline built+validated this
  session): feature drift |cum_k_pct| mean 0.0004, median 0, p99 0.0084, **max 0.012**
  (1.2 K-rate points); **0 pitchers** drift >2 points. Reason: the window is only ~4 days
  (≈1 missed start) — veterans on large cumulative samples are unmoved; only small-sample
  rookies move, and ≤1.2 points. **3 pitchers debuted after 06-06** (Warren/Austin 681810,
  Bennett/Jake 687562, Jump/Gage 695611) → served as missing→fallback (the sharper exposure,
  but only 3, and none of them appear in any published pick).
- **Candidate-pool exposure (ADR-035 class):** the whole in-window candidate set was
  generated on frozen features, but with median drift 0 / max 1.2 K-points, few tag flips
  are possible. Real but low-magnitude because caught ~5 days post-cutover (months of
  staleness would have been severe). Not catastrophic, not negligible.

**Published-pick zero-flip verification (the 7, re-derived on corrected v2-scratch):**
all 7 tags UNCHANGED. 4 MLRL are `MLRL_STREAK_ELITE` — *verified* independent of
`pitcher_cumulative_v2` (26e tags on team losing-streak + away ML, not pitcher features).
3 totals UNDER tags — *inferred* unchanged: their starters' K% drift was ≤0.003 (Cole/Cecconi,
Holmes/Fedde, Singer/King), a <0.05-run shift in predicted_total, well inside the tag margins;
none of the 3 debut/fallback pitchers start any of the 7. **ZERO flips — the 7 published bets
stand as-made.** No tracker mutation performed.

This does NOT explain the full-season K drawdown (−63u/948 bets): the stale window is only
06-07→present; the March–May bulk predates the cutover on fresh v1 substrate.

## Fix (applied + verified 2026-06-12)

1. **Wired** `06a_v2_cumulative_pitcher_metrics.py` into `resolve_morning.bat` [5/8],
   immediately after the v1 06a (after 05d Statcast refresh, before pregame's v2 readers),
   with the standard `errorlevel` abort guard. Placement mirrors v1's cadence; correct
   because 06a_v2 depends on `pitches_historical`, not on pregame data.
2. **Hardened persistence (A3 atomicity guard, ADR-046 §A.3 class):** replaced the raw
   `DROP + to_sql(if_exists="replace")` with **build-to-scratch → row-count floor
   (≥95% of live) → atomic DROP+RENAME swap**. A degraded/partial build aborts with the
   live table UNTOUCHED; a mid-write crash cannot leave it empty. The validated compute
   (identify_starter_games / compute_pitcher_cumulative_v2) is byte-unchanged.

**Pre-wire validation (load-bearing):** built 06a_v2 to an isolated scratch DB (live DB
read-only) and overlap-diffed vs v1 — +354 rows (matches ADR-045's "+352"), no all-null
cores, 60% identical / 40% v2>v1 / **0 v2<v1**; divergence fully explained by the ADR-028
relief-pitch fix. Builder VALIDATED before wiring.

**Post-apply LIVE verification:** `pitcher_cumulative_v2` = **15,611 rows, MAX(game_date)
2026-06-10**; overlap-diff on the live table 15,257 shared → 60.1% identical, 6,089 v2>v1,
**0 v2<v1**; no stray `__new` table (swap clean); floor guard + atomic swap present in the
live file; no dry-run/`--apply` trap (write confirmed). *(all verified-by-measurement)*

## Production-run confirmation (Session 47, 2026-06-12) -- verified-by-measurement

06a_v2 ran in the DAILY `resolve_morning.bat` [5/8] (the wired step). As
`pitches_historical` advanced to 2026-06-11, the atomic-swap rebuild produced
`pitcher_cumulative_v2` = **15,625 rows, MAX(game_date) 2026-06-11** (verified in the live
DB). Overlap-diff on the PRODUCTION table vs v1: 15,271 shared keys, **0 rows v2<v1** (9,176
identical, 6,095 v2>v1) -- the relief-fix invariant holds on the production rebuild (+354 vs
v1, consistent with ADR-045's "+352"). Backup retained:
`pitcher_cumulative_v2_bak_unwirefix_20260612_083902`.

CAVEAT (accuracy correction): the resolve_morning batch did NOT complete cleanly. The v2
DATA write succeeded (atomic swap; table updated), but the run later raised a `pull_log`
UNIQUE-constraint error and aborted before the dashboard step -- cause: 06a_v2's `log_pull()`
uses a non-timestamped `chunk_id` that collides on repeat runs (no v2 audit row written today;
only v1 entries). Data integrity unaffected; batch tail broken. Tracked as a Session-47 open
item (see ROADMAP) and in "Known notes" below. The "15,611 rows @ 06-10" figures earlier in
this ADR are the pre-production manual-run verification; the production figures above are the
current live state.

## Known notes / follow-ups (not blocking; each its own task)

- **cp1252 banner:** `06a_v2`'s startup banner uses box-drawing Unicode (as does v1 06a,
  which runs SUCCESS daily). It crashes under a cp1252-only console (my interactive run;
  re-run under `-X utf8`). Production runs it as it runs v1 — not a production blocker.
  Optional hardening: ASCII-ify both banners (ADR-046 §A decode discipline).
- **pull_log audit:** `06a_v2.log_pull` builds a non-timestamped `chunk_id`, so its
  pull_log insert hits a UNIQUE collision on repeat runs (non-fatal, table unaffected).
  Minor: timestamp the chunk_id like other writers.
- **G1 boundary:** `pitches_historical` max is 06-10 (06-11 not yet pulled; the 06-12
  Statcast pull was absent and `05a_enrichment` FAILED 06-10/06-11 — chronic FanGraphs 403,
  orthogonal to v2). The rebuilt v2 is fresh THROUGH 06-10. Ensure today's Statcast pull
  lands 06-11 for fully-clean tagging of any 06-11→06-12 back-to-back starter (immaterial
  per the magnitude above).

## Operational answer (Part D)

After this fix, tonight's (06-12) slate **can be tagged on corrected, fresh-through-06-10
substrate for K, totals, and MLRL** (bullpen inputs already fresh via §B, 06-11). The only
residual is the 06-11 pitch data not yet pulled (G1), whose impact is immaterial (≤1 missed
start, ≤1 K-point). Run today's Statcast pull first for a fully-clean slate.

## Rollback

Files: `resolve_morning.bat.bak_unwirefix_20260612_083902`,
`06a_v2_cumulative_pitcher_metrics.py.bak_unwirefix_20260612_083902`.
Table: `DROP TABLE pitcher_cumulative_v2; CREATE TABLE pitcher_cumulative_v2 AS SELECT *
FROM pitcher_cumulative_v2_bak_unwirefix_20260612_083902;` (frozen 06-06 snapshot retained).

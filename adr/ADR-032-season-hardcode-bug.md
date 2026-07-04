# ADR-032: season=2025 Stale-Substrate Bug Class

**Date:** 2026-05-17
**Status:** Active patch — Session 32
**Severity:** P0 system-wide. Confirmed model-bleed root cause.
**Pattern:** S6 (population-mixing / stale-substrate read). Sibling of ADR-031.

---

## Context

Starting 2026-W18 (May 7), the published-picks model began bleeding
sharply. Documented in this session's diagnostic
(`diag_published_picks_full_season.py`):

| Window | N | WR | P&L | ROI |
|---|---|---|---|---|
| Through 2026-W17 (4/4 – 5/2) | 85 | 56.5% | +9.92u | +11.7% |
| 2026-W18 + W19 (5/7 – 5/16) | 24 | 29.2% | -10.22u | -42.6% |

Season P&L: +15.13u peak on 4/30 → -0.30u on 5/16. Max drawdown -15.43u
in 16 days. Bias signature in resolve summary:

- Totals MAE 3.69 (backtest 3.51), bias **-0.17 runs** (backtest +0.08)
- K props MAE 1.96 (backtest 1.86), bias **-0.33 K** (backtest +0.15)

Both biases flipped sign. The model is now systematically under-
predicting both totals and Ks, which means the unders it picks
underperform.

## Root Cause

Two production scripts (`05c_pregame_context.py` and
`07_predict_today.py`) hardcode `season = 2025` in either default
function arguments or SQL filter clauses. Despite 2026 substrate
being available (mid-May 2026 has ~5,500 pitches per team in
`bullpen_stats(2026)` and 30 teams populated), every production read
in these scripts returns the 2025 row when both seasons exist.

The bug class is the same as ADR-031 (BP staleness fallback):
read with no awareness of population boundary, fall through to
stale data, produce silently corrupted features.

### Confirmed instances

**`05c_pregame_context.py` L435** — `get_bullpen_availability(..., season=2025)` default arg.
- Verification: `diag_verify_session31_finding1.py` — 120/120 game_context
  rows in last 14 days store `home_bp_fip` / `away_bp_fip` values that
  match `bullpen_stats(season=2025)` exactly, never `bullpen_stats(season=2026)`.
- Mean |ΔFIP| between seasons = 0.341; max 0.94 (HOU 5.03 → 4.09).
- Affected fields: bp_fip, bp_xfip, bp_k_pct, bp_woba_allowed,
  bp_xwoba_allowed (5 columns × home/away × every 2026 game written).
- Downstream consumers: 22l, 26e, 27i, 28i (all read `game_context.*_bp_*`).

**`07_predict_today.py` L90** — `WHERE pitcher_id = ? AND season = 2025` on `pitcher_cumulative`.
- Verification: `diag_verify_07_and_inspect_03c.py` — 25/28 of today's
  starters have both 2025 and 2026 rows in pitcher_cumulative;
  exact-reproduction of 07's query returns the 2025 row in every case.
- Affected fields: cum_bf, cum_games, cum_k_pct, cum_bb_pct,
  cum_whiff_rate, cum_avg_bf_per_start, cum_k_pct_tto1/2/3,
  cum_k_pct_vs_L, cum_k_pct_vs_R, cum_xwoba_allowed, cum_barrel_pct,
  cum_csw_rate, cum_chase_rate, cum_k_bb_pct, cum_avg_pitches_per_start,
  cum_ip, pitcher_throws (19 fields).
- Magnitudes observed today: Zack Wheeler K% 0.332 (2025) vs 0.232 (2026),
  10pp overstatement. Brady Singer 0.228 → 0.142, 8.6pp. Grant Holmes
  0.250 → 0.192, 5.7pp (this is a today-tagged K_OVER_WHIFF_VULN candidate).
- Downstream consumers: all K prop predictions in `bet_tracker`, every
  K prop tag in `27i_k_prop_tagger.py`.

### Same-class instances (likely not biting today, fixed for consistency)

**`05c_pregame_context.py` L228** — `build_lineup_composite(..., season=2025)` default arg.
- Verification (indirect): last-14d game_context lineup composite K%
  distribution mean = 0.222, which matches the 2026 hitter pool mean
  (0.222) rather than 2025 (0.235). This suggests the caller passes
  season explicitly and the default does not fire — but the bug class
  is identical to L435 and we are removing the dangerous default for
  consistency.

**`07_predict_today.py` L116** — `WHERE pitcher_id = ? AND season = 2025` on `pitcher_stats` fallback path.
- Same SQL bug class as L90 in the fallback function
  `get_pitcher_stats_fallback()` called when pitcher_cumulative returns
  no row. Fired today for Peter Lambert and Elmer Rodríguez (no
  cumulative entries yet).

## Scope Decision

### In scope for this ADR (4 production-poisoning hits)

1. `05c_pregame_context.py` L228 default arg
2. `05c_pregame_context.py` L435 default arg
3. `07_predict_today.py` L90 SQL filter
4. `07_predict_today.py` L116 SQL filter

### Verified NOT in scope (19 hits, all confirmed display-only)

`diag_classify_03abcd_and_21_hits.py` verified every flagged hit in:
- 03a_pitcher_metrics.py (L697, L713, L720, L732) — all in VERIFICATION
  section after all writes (last write at L675)
- 03b_hitter_metrics.py (L493, L505, L517, L531, L543) — all in
  VERIFICATION section after L467 write
- 03c_team_aggregations.py (L523, L536, L548, L560, L571) — all after
  L497 final write
- 03d_regression_flags.py (L407, L421, L434, L446) — all after L380
  final write
- 21_weekly_validation.py (L368) — file has zero writes; feeds
  `print_check()` only. Currently uses 2026 (correct year).

These 19 hits are P3 cosmetic. They will produce mislabeled terminal
output ("Top 10 bullpens (2025)") but cannot poison data. Deferred
to a separate batched hygiene cleanup.

### Substrate provenance verified

`diag_audit_season_2025_pipeline_wide.py` CHECK D confirmed
`bullpen_stats(2026)` has 5,354-6,327 pitches per team (well above
1,000 threshold for stable rates). 03c writes are season-agnostic
(`if_exists="replace"` with current-pull dataframes), so the 2026
substrate was correctly written even though display labels say 2025.
The corrected substrate is trustworthy and usable immediately.

## Patch Approach

### 07_predict_today.py (L90, L116) — per-pitcher max(season)

Replace the `season = 2025` literal with `ORDER BY season DESC` style,
matching the already-correct pattern in `11_predict_totals.py` L228+
and `11b_predict_mlrl.py` L365+. This is defensive because:

- Some pitchers have only 2025 data (e.g., Robert Gasser today)
- Some pitchers have only 2026 data (e.g., rookies, Peter Lambert today)
- Most established pitchers have both; we want the newest available

L90 (pitcher_cumulative, has game_date column too):

```python
# Before
WHERE pitcher_id = ? AND season = 2025
ORDER BY game_date DESC
LIMIT 1

# After
WHERE pitcher_id = ?
ORDER BY season DESC, game_date DESC
LIMIT 1
```

The existing `ORDER BY game_date DESC LIMIT 1` was already there — we
just elevate season to the primary sort key. This is a minimal change.

L116 (pitcher_stats fallback, no game_date):

```python
# Before
WHERE pitcher_id = ? AND season = 2025
LIMIT 1

# After
WHERE pitcher_id = ?
ORDER BY season DESC
LIMIT 1
```

### 05c_pregame_context.py (L228, L435) — compute CURRENT_SEASON

Add a module-level constant computed from `datetime.now().year` and
use it as the function default. Self-updating; survives the
2026→2027 boundary without code change.

```python
# At top of file with other constants
CURRENT_SEASON = datetime.now().year

# L228
def build_lineup_composite(lineup, starter_throws, conn, season=CURRENT_SEASON):

# L435
def get_bullpen_availability(team, game_date, conn, season=CURRENT_SEASON):
```

Edge case considered: in early March before opening day,
`datetime.now().year` returns the new calendar year when no games
have been played yet. `bullpen_stats(season=N)` rows are only
populated by 03c when there is pitch data for season N — so the
function would return None and the existing None-handling paths in
the callers would fire. This is correct behavior; it forces the
operator to deal with empty BP context for preseason rather than
silently substituting last year's bullpens.

### Backfill Decision: NO

Historical `game_context` rows written before this patch contain
2025 bp_* values for 2026 games. Historical `bet_tracker.predicted_k`
values are derived from 2025 pitcher_cumulative reads for 2026 games.

Two options were considered:

- **A. Leave historical, mark window as poisoned.** Future edge
  re-validation and backtest work filters out 2026-04-04 through
  2026-05-17 (inclusive) as "ADR-032 substrate-poisoning window."
- **B. Backfill.** Re-run 05c, 07, 22l, 26e, 27i, 28i for every date in
  the window with corrected substrate. Regenerate game_context, re-tag,
  re-resolve.

**Chosen: A.** Reasoning:
- B is a multi-session project that interleaves with daily operations.
- Historical bet results are already known; the picks were either tagged
  or not, won or lost. Re-tagging them doesn't change the recorded
  outcomes.
- The substrate-poisoning window is well-defined and short
  (~6 weeks). It can be cleanly excluded from future validation work.
- Forward-track from the patch date is what matters for live performance
  validation. The patch creates a clean cutpoint.

## Validation Plan

After patch applied:

1. Re-run `diag_verify_session31_finding1.py`. Expect 0/120 matches
   for 2025 on NEW game_context rows, 100% match for 2026. (Old rows
   will still match 2025 — they're not being rewritten.)
2. Re-run today's `05c_pregame_context.py` and confirm bp_fip values
   in `game_context` for 2026-05-17 now match `bullpen_stats(2026)`.
3. Re-run today's `07_predict_today.py` and confirm K predictions
   change for the 25 starters with 2026 cumulative data. Magnitude of
   K% shift should be 1-10pp for affected pitchers.
4. Re-run today's `pregame_pipeline.bat` (08, 22l, 26e, 27i, 28i).
   Tag set will likely change materially. Document the diff.
5. Forward-track from 2026-05-17 onward. Tag-level performance numbers
   from before this date are not comparable to post-patch numbers.

## Memory Updates Required

After patch application:

1. Update Session 31 Audit Finding #1 from "DEFERRED HIGH" to "RESOLVED 2026-05-17 ADR-032."
2. Mark ROADMAP.py latent bug "`season = 2025` hardcoded on lines 90 and 116 of 07_predict_today.py" as RESOLVED.
3. Add to DECISIONS.py: 2026-04-04 through 2026-05-17 is the
   "ADR-032 substrate-poisoning window." Pre-window tag performance
   numbers are not comparable to post-window.
4. Add to RULES_FOR_CLAUDE.py: when adding any code that reads a
   season-partitioned table (pitcher_stats, pitcher_cumulative,
   bullpen_stats, hitter_stats, team_offense, etc.), use
   `ORDER BY season DESC LIMIT 1` or a computed `CURRENT_SEASON`
   constant. **Never** a hardcoded year literal.

## Patch Artifacts

- Patch script: `patch_adr_032_season_hardcode.py`
  - Targets: 05c_pregame_context.py (L228, L435), 07_predict_today.py (L90, L116)
  - Atomic, with backup files
  - `--dry-run` is the default; `--apply` to commit
  - Post-write `ast.parse()` verification on both patched files
  - Auto-restore on parse failure
- Backup naming: `<filename>.bak.adr032.<timestamp>`
- ADR file: `docs/adr/ADR-032-season-hardcode-bug.md` (this file)

## Open Items After Patch

- P3 hygiene: 19 display-only `season = 2025` references in 03a/b/c/d/21.
  Schedule a batched cleanup pass. Not urgent.
- FanGraphs 403 (recurring this morning). Separately deferred — `audit later`
  per operator instruction this session. Still pending investigation.
- 21_weekly_validation.py L368 hardcoded `season = 2026` will rot in
  2027. Same hygiene bucket.
- Forward-track: minimum 20 picks under post-patch substrate before
  any tag-level claims about restored performance.

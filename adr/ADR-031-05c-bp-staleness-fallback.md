# ADR-031: 05c BP silent staleness fallback — Pattern S6 fix

Status: Accepted
Date: 2026-05-14
Session: 30 (diagnosis + fix); documented 2026-05-15 Session 31

## Context

`05c_pregame_context.py` builds the per-game `game_context` table
that downstream taggers (28i, 22l, 26e, 27i) read at tag time. Among
many fields, it writes `away_bp_pitches_prior_3d` and
`home_bp_pitches_prior_3d` for each game — the trailing-3-day
bullpen workload values that 28i uses as the freshness gate for
`OUTS_UNDER_STRONG` and `OUTS_UNDER_ELITE` tags.

Until Session 30, `get_bullpen_availability` (the 05c helper that
populates these fields) read from `bullpen_workload` with this
pattern:

```sql
SELECT bp_pitches_prior_3d, ...
FROM bullpen_workload
WHERE team = ? AND game_date <= ?
ORDER BY game_date DESC
LIMIT 1
```

The `<=` plus `ORDER BY DESC LIMIT 1` is a **silent staleness
fallback**: if no row exists for the exact target date, the query
returns the most recent prior row instead. The caller had no way
to tell whether the value it received was for the exact date or
days old, and 05c wrote it into `game_context` without any
freshness marker.

### Backtest semantics, by contrast

The backtest substrate `28g_outs_backtest.py` (which produced the
58% WR figure for OUTS_UNDER_STRONG and 64.5% for OUTS_UNDER_ELITE)
joined `outs_historical` to `bullpen_workload` on **exact game_date
match** and dropped rows where the join produced NaN. Backtest
semantics never substituted prior-day BP for missing same-day data.

The live tagger 28i therefore was applying the documented filter
(`bp_pitches_prior_3d <= P20`) to data the backtest substrate would
have **excluded entirely**.

### Discovery

During Session 30, an OUTS_UNDER_STRONG live underperformance
investigation found:

- Post-alignment record (post 2026-04-20, the ADR-023 outs team-swap
  fix): 9W-12L (-3.17u) across 21 picks.
- Of those 21 picks, **7 were tagged on dates where bullpen_workload
  had no row at all** (5/11, 5/12, 5/13, 5/14). All 7 fired with
  NULL BP after Fix A landed, meaning under the corrected semantics
  they would have been untagged.
- Of the **14 picks where BP data did exist**, 10 fired on bullpens
  measured at >P30 of the trailing-30-day distribution — clearly
  not "fresh" by the documented filter. Investigation showed these
  were tagged using stale-fallback BP values (the silent
  substitution) that happened to fall below the dynamic P20
  threshold *as the substituted value*, not as the actual same-day
  value.

The 9W-12L post-alignment number was therefore a **mixed-population
artifact**, similar in spirit to the ADR-030 finding for
edge_monitor: an aggregate produced by combining picks tagged under
different effective filters.

### Diagnostic chain

1. `check_bullpen_staleness.py` confirmed `bullpen_workload` had no
   rows for 2026-05-11 through 2026-05-14, despite resolve_morning
   running daily during that window.
2. Reading 03c-equivalent logic in 05d_weekly_refresh confirmed that
   the weekly Statcast pull was not part of the daily resolve, so
   pitches_historical and downstream `bullpen_workload` only
   refreshed on manual weekly runs (Mondays).
3. Reading 05c_pregame_context.py revealed the `<=` ... `ORDER BY
   DESC LIMIT 1` pattern in `get_bullpen_availability` (line ~467).
4. Reading 28i_outs_pipeline.py confirmed the tagger had no
   defensive null-or-staleness check — it took whatever
   `game_context` gave it and applied the P20 filter.

## Decision

Three coordinated fixes, all landed Session 30 (2026-05-14):

### Fix A — 05c exact-date BP read

Replace the `<=` ... `ORDER BY DESC LIMIT 1` query in
`get_bullpen_availability` with an exact-date match:

```sql
SELECT bp_pitches_prior_3d, bp_batters_prior_3d,
       bp_games_prior_3d, bp_workload_flag
FROM bullpen_workload
WHERE team = ? AND game_date = ?
```

If no row exists for the exact date, all four BP workload fields
are left as `None`. Downstream consumers (28i) already skip rows
where `bp_pitches` is None — the tagger's existing null-guard now
becomes the load-bearing protection.

Code change documented inline at 05c lines 459-466 with a comment
block referencing this ADR.

### Fix B — daily pitches_historical refresh

Add `05d_weekly_refresh.py` (in `--auto` mode with a 1-day gap
detection) to `resolve_morning.bat` as step `[4/7]`. This ensures
`pitches_historical` and downstream `bullpen_workload` refresh
every morning, not just Mondays. First production run was
2026-05-15 morning — completed cleanly, 3,193 pitches pulled for
2026-05-14, all Phase 2 metrics rebuilt, `bullpen_workload` current
through 2026-05-14.

### Fix B' — today's-row bridge in pregame

`bullpen_workload` is keyed by `(team, game_date)`, and today's row
cannot be written by 03c because today's pitches haven't happened
yet. To bridge this gap, `populate_today_bp_workload.py` was
written: for each team playing today, it computes
`bp_pitches_prior_3d`, `bp_batters_prior_3d`, `bp_games_prior_3d`,
and `bp_workload_flag` from prior rows already in `bullpen_workload`
and inserts today's row with `bp_pitches_today = 0` (since the game
hasn't happened). It is idempotent (replaces today's row on re-run),
read-only on `pitches_historical`, write-only on `bullpen_workload`.

This script is called from `pregame_pipeline.bat` as step `[0/7]`,
before 05c, per the patch landed 2026-05-15 Session 31
(`patch_pregame_bp_bridge.py`). If the bridge fails, the bat file
aborts with `exit /b 1` before 05c can read stale data.

### Re-grade

23 bets were identified as candidates for re-grading under the
corrected semantics. Of those, **22 were untagged** (clv_tag set
to NULL) because the BP value that originally triggered the tag
was a stale fallback. **1 KEEP**: the bet where the same-day
exact-match value would have qualified under the corrected
semantics. Re-grade preserved a JSON backup of the original
clv_tag values.

## Consequences

### Forward-tracking restart

OUTS_UNDER_STRONG and OUTS_UNDER_ELITE live records reset
effectively to zero as of 2026-05-14 under the corrected semantics.
The post-rebuild stat readout from 2026-05-15 morning resolve
showed OUTS_UNDER_STRONG at 8W-3L (+4.42u, 72.7% WR) — this is a
**post-regrade n=11 figure**, not a long-history performance
number, and should not be compared to the 58% backtest target until
sample size matures (target n=30+ for first directional read,
n=60+ for stability check).

### Live ADR-030 implications

ADR-030 already required edge_monitor to be alignment-aware. The
ADR-031 fix introduces a **new alignment date for OUTS_***
(2026-05-14) on top of the existing ADR-023 alignment date
(2026-04-20). Both alignment dates must be registered in
edge_monitor's `ALIGNMENT_DATES` mapping. Logged as a follow-up.

### Related instance — same bug class

While auditing for Pattern S6 instances in adjacent code (Session
31, 2026-05-15), the following **second instance** of the same
bug class was found in the same file:

**05c line 435**: `def get_bullpen_availability(team, game_date,
conn, season=2025)`.

The `season=2025` default value is stale. The single caller at
line 644 does not pass `season` explicitly, so every 2026 lookup
reads `bullpen_stats` for the **2025 season**, not 2026:

```python
SELECT bp_fip, bp_xfip, bp_k_pct, bp_woba_allowed,
       bp_xwoba_allowed
FROM bullpen_stats
WHERE team = ? AND season = ?
```

This affects `bp_fip`, `bp_xfip`, `bp_k_pct`, `bp_woba_allowed`,
`bp_xwoba_allowed` — the bullpen *quality* features (distinct from
the *workload* features fixed by Fix A). The downstream impact:
- 22l, 26e, 27i read these fields from game_context when scoring
  edges. They are using 2025 bullpen quality stats for every 2026
  game.
- Quantitative impact unknown until sample bullpen_stats rows are
  inspected.

This is the **same bug class** as the BP workload fallback — a
hardcoded value silently substitutes wrong-period data when the
caller doesn't override it. The fix is trivial (remove the default
or set it from `game_date`) but the assessment of how many edges
this has affected requires looking at how 2025 vs 2026 bullpen
quality differs.

**Decision: fix logged as Audit Finding #1, scope/fix deferred to
a dedicated patch in next session.** Not bundled with this ADR's
fixes because (i) the bug pre-dates ADR-031's investigation by an
unknown duration, (ii) all live edge tags that depend on bullpen
quality features need re-validation under the corrected season,
and (iii) the diagnostic work belongs to a separate workstream.

## Pattern S6 generalization

The shared pattern across ADR-030, ADR-031, and the related Finding
is: **a code path that silently substitutes default or fallback
data when the requested data is unavailable, without surfacing the
substitution to the caller, and where downstream code applies
filters or thresholds as if the substituted data were the real
thing.**

Specific code-shape variants to audit:

1. `WHERE col <= ? ORDER BY col DESC LIMIT 1` against a daily-keyed
   table (this ADR's primary instance).
2. Function arguments with hardcoded year/season defaults
   (`season=2025`) where callers don't override.
3. `if X is None: X = fallback_constant` patterns where
   `fallback_constant` was set against a specific snapshot of data.
4. SQL `COALESCE(col, default)` with stale defaults.
5. JSON/dict `.get(key, default)` reads against
   slowly-evolving data structures.

Other audit findings from the Session 31 audit pass are documented
in ROADMAP.py "On the horizon" with file:line references.

## Validation

### Pre-deployment

- `populate_today_bp_workload.py` tested in dry-run for 2026-05-14
  before --apply. Each team's prior-3d window computed correctly
  against historical bullpen_workload rows.
- Fix A code change verified: re-ran 05c on 2026-05-14, confirmed
  that teams without same-day BP rows received None values, and
  that 28i correctly skipped those bets.
- Re-grade script preserved JSON backup of pre-regrade clv_tag
  values for all 23 candidate rows.

### Post-deployment

- 2026-05-15 morning resolve: first production run of patched
  `resolve_morning.bat` with 05d auto-refresh in the chain. 05d
  detected the 1-day gap, pulled 3,193 pitches for 2026-05-14,
  rebuilt 03a/b/c/d, refreshed all Phase 2 metrics. Database
  freshness report showed `bullpen_workload` current through
  2026-05-14 with 15,589 rows.
- 2026-05-15 Session 31: `patch_pregame_bp_bridge.py` applied with
  full backup + verify + idempotency check passing.

### Forward monitoring

- OUTS_UNDER_STRONG: forward-track from 2026-05-14. Demote rule:
  WR < 50% at n=30+ post-alignment.
- OUTS_UNDER_ELITE: forward-track from 2026-05-14. Demote rule:
  WR < 55% at n=20+ post-alignment.
- Daily sanity: after each resolve_morning, verify
  `MAX(bullpen_workload.game_date) = yesterday`. If not, halt
  pregame.
- Each pregame run: verify
  `COUNT(*) FROM bullpen_workload WHERE game_date = today` equals
  the count of teams in today's `daily_games`. If not, the
  bridge failed silently.

## Follow-ups (not blocking)

- **05c season=2025 default arg (Finding #1)**: fix scope and
  decide whether re-validation of all bullpen-quality-dependent
  edges is required. Track separately.
- **ADR-031 alignment date for edge_monitor**: register 2026-05-14
  as alignment date for OUTS_UNDER_STRONG and OUTS_UNDER_ELITE in
  edge_monitor.py `ALIGNMENT_DATES`.
- **Audit Findings #2-#6**: documented in ROADMAP "On the horizon"
  with file:line references and severity tags.
- **populate_today_bp_workload.py edge cases**: behavior when a
  team has 0 prior-3d games (e.g., season opener) is to set
  `bp_pitches_prior_3d = 0` and `bp_workload_flag = NORMAL`. This
  is intentional (fresh = good for the under-edge thesis) but
  worth a forward-track note.

## References

- `RULES_FOR_CLAUDE.py` Pattern S6 — this ADR closes a specific
  instance of the silent-substitution pattern.
- `docs/adr/ADR-023-outs-team-swap-root-cause.md` — prior
  OUTS_* alignment, 2026-04-20.
- `docs/adr/ADR-030-edge-monitor-alignment-awareness.md` — same
  Pattern S6 class, in edge_monitor rather than 05c.
- `05c_pregame_context.py` (Fix A site, lines 435-493).
- `populate_today_bp_workload.py` (Fix B' bridge script,
  E:\mlb_model root).
- `patch_05c_bp_exact_date.py` (Fix A patch script, Session 30).
- `patch_resolve_morning_05d.py` (Fix B patch script, Session 30).
- `patch_pregame_bp_bridge.py` (Fix B' batch-file patch, Session 31).
- `28g_outs_backtest.py` — backtest substrate establishing exact-
  date BP join semantics.
- Session 30 transcript (2026-05-14): diagnostic chain, re-grade
  execution, 22 bets untagged.
- Session 31 transcript (2026-05-15): audit pass, ADR drafting,
  Finding #1 discovery.

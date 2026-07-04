# ADR-046: Session 46 incident chain — Statcast schema-drift, bullpen_workload_v2 zero-collapse, OUTS publish-suppression

Status: Accepted
Date: 2026-06-10
Session: 46
Relates to: ADR-043 (v2 not wired / live contamination), ADR-044 (OUTS_UNDER
            demotion on v2), ADR-045 (v2 serving cutover). **This ADR SUPERSEDES
            ADR-045's characterization that `28i_outs_pipeline.py` "reads
            bullpen_workload (v1)" for the OUTS BP *tag input*** — see B-note.

> All findings below were verified first-hand against the live repo / DB on
> 2026-06-10 (read-only traces; row-count checks, not just exit codes).

## A. Statcast `miss_distance` schema-drift crash + 05d hardening

Root cause: Baseball Savant added column `miss_distance` to the Statcast feed
(pybaseball 2.2.7 passes it through). `05d_weekly_refresh.py`'s
`pull_statcast_range()` did `to_sql(..., if_exists='append')` with no column
whitelist, so the unknown column broke the insert and `resolve_morning.bat`
aborted at the pull step. The abort guard worked as designed: substrate was
correctly NOT rebuilt on a stale/failed pull.

Fixes landed (all in `05d_weekly_refresh.py` unless noted):
1. Idempotent migration (`ensure_schema()`) adding `miss_distance REAL` to
   `pitches_historical`, committed BEFORE the pull's drift guard reads a fresh
   `PRAGMA`.
2. New `schema_drift_log` table + a pre-write column-drift guard in
   `pull_statcast_range()` that HALTS on any future unknown column (logs a
   durable row, prints a banner, `sys.exit(1)`, modifies zero data) — requiring
   operator sign-off before a new column enters the table.
3. Atomic delete+insert keyed only to the dates actually returned by the feed,
   fixing two latent silent-data-loss bugs: (a) the old delete-then-`commit`
   before insert (a failed insert had already destroyed rows); (b) deleting the
   requested range while inserting only the returned range (a lagging date could
   be deleted and never replaced). Date strings normalized to the stored
   `YYYY-MM-DD` format first.
4. Subprocess decode hardening in `recalculate_metrics()` and
   `refresh_fangraphs()`: `encoding='utf-8', errors='replace'` + None-guards on
   the three stdout/stderr access points, so a future UTF-8-mode/cp1252 mismatch
   cannot crash logging or mask a successful recalc.

CORRECTION of an earlier same-session belief: the `UnicodeDecodeError` seen
during recalc was NOT a production recalc failure. It was a self-inflicted
artifact of running 05d under `python -X utf8` (parent decoded child cp1252
output as UTF-8). Production (`resolve_morning.bat` -> plain `python
05d_weekly_refresh.py`, cp1252 both sides) does not hit it; verified against
`resolve_morning.bat`. The recalc children exited 0 and wrote correctly; a clean
re-run of 03a-03d returned ALL-CLEAN.

Outcome: `pitches_historical` fresh through 2026-06-09; 03a-03d (and the
operator's subsequent 06a/06b) rebuilt clean. Verified by row count
(`game_date='2026-06-08'` non-zero: 2,600 pitches), not just exit code.

## B. `bullpen_workload_v2` all-zeros regression (today-row collapse)

Symptom: on 2026-06-10 `populate_today_bp_workload.py` computed v2
`bp_pitches_prior_3d = 0` for all 30 teams while v1 was correct.

Root cause: at the ADR-045 cutover (2026-06-07) serving reads were moved to v2,
but the v2 BUILDER `03c_team_aggregations_v2.py` was never wired into the daily
rebuild chain (v1's `03c_team_aggregations.py` runs daily inside 05d's recalc;
`03c_v2` ran in no pipeline). After cutover the only writer of v2 rows was
`populate_today_bp_workload.py`, which stamps `bp_pitches_today=0` for the
unplayed today-row; nothing backfilled the real value. The prior-3-day window
sums `bp_pitches_today` from prior v2 rows, so it walked forward over
accumulating placeholder zeros: avg 161 (06-07) -> 108 (06-08) -> 63 (06-09)
-> 0 (06-10). v1 was immune because 03c rebuilds it daily.

Independent of the day's `miss_distance` work (verified): the collapse date is
pure cutover + 3-day-window arithmetic and predates the morning's substrate
work; `03c_v2` does not even read `pitches_historical` in the daily path.

Fix landed (Option B): inserted step `[1a/8] python
03c_team_aggregations_v2.py` in `pregame_pipeline.bat`, BEFORE the populate
step. Mandatory order: 03c_v2 rebuild (`if_exists='replace'`, repairs the
06-07->06-09 history in place) -> populate bridges today's row -> 05c reads.
Pregame placement was chosen over 05d placement for robustness to a
`resolve_morning` abort (the very failure mode that triggered this incident).
First real writing run is the next clean pregame (2026-06-11); the fix is
UNVERIFIED against live data until then.

### B-note — SUPERSEDES ADR-045's "28i on v1" (for the BP tag input)
ADR-045 (section "Intentionally left on v1") states `28i_outs_pipeline.py`
"still reads `bullpen_workload` (v1, L360)" and calls it a "Known remaining v1
reader." A read-only trace this session proved that for the OUTS *tag decision*
this is misleading: `tag_outs_edges()` reads BP from
`game_context.{home,away}_bp_pitches_prior_3d` (which 05c populates from
`bullpen_workload_v2`), and the v1 `bullpen_workload` read is ONLY a fallback
guarded by `if not bp_data:` — which does NOT fire post-cutover, because 05c
writes integer `0` (not NULL) from the contaminated v2 row, leaving `bp_data`
populated. The threshold (`_compute_rolling_bp_p20()`) ALSO reads
`game_context`. So the OUTS tag input is v2-derived, not v1. ADR-045's
parenthetical "its primary BP input is `game_context` (now v2 via 05c)" was
correct; its headline "reads `bullpen_workload` (v1)" / "Known remaining v1
reader" is SUPERSEDED for the tag-input question. (ADR-045 remains literally
accurate that 28i still CONTAINS a v1 read — it is simply dormant.)

## C. OUTS dead-market publish suppression

Problem: `19_publish_picks.py` offered OUTS entries as selectable/publishable
despite OUTS being a dead market (ADR-044: demoted, never bet).

Fix landed (selection-layer, not just relabel): a load-bearing reject in
`publish_picks()` refuses any pick with `source_table == 'outs_tracker'` BEFORE
the INSERT (so even a directly-typed OUTS number writes nothing), plus menu
suppression in `main()` and a cosmetic header relabel in 28i. Matched on the
STRUCTURED field `source_table == 'outs_tracker'` (NOT `market == 'props'`,
which is shared with K-props). OUTS tagging / tracking / resolution are left
fully intact per ADR-044's deliberate audit-data retention. Regression-tested
against an in-memory DB (OUTS refused; non-OUTS still publishes); no live
publish.

## D. KNOWN DATA-QUALITY CAVEAT — OUTS tracker 2026-06-08 -> 2026-06-10

Because the OUTS tagger gates on BP from the contaminated `game_context` (B-note
above), OUTS tracker entries tagged 2026-06-08 -> 2026-06-10 were computed on
degraded/zero BP. The gate `fresh_bp = bp <= p20` is trivially true at `bp=0`,
so OUTS_UNDER STRONG/ELITE OVER-FIRED on those dates. Entries on/before ~06-07
are clean. Tomorrow's v2 rebuild (fix B) repairs the table and ALL FUTURE tags
but does NOT retroactively re-tag those already-written 06-08->06-10 rows.

Status: known caveat, NOT remediated. OUTS is a dead market (not bet), so no
P&L impact; re-tag is optional pending operator decision. If OUTS tracker
history is ever used to assess re-validation, treat 2026-06-08 -> 2026-06-10 as
suspect.

## Consequences / status
- Schema-drift is now fail-loud, not silent: the next unknown Statcast column
  halts 05d with operator sign-off required.
- v2 is maintained daily from the next clean pregame; v1/v2 freshness no longer
  diverges via the populate placeholder path.
- OUTS cannot enter `published_picks` by any selection path.
- No serving/code change was made by THIS record (docs-only); fixes A-C landed
  earlier in the session and are recorded here.

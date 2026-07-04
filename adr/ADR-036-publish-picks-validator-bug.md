# ADR-036: 19_publish_picks.py Validator Schema Mismatch — Patched

**Status:** Accepted
**Date:** 2026-05-24 (Session 37)
**Affected file:** `19_publish_picks.py`

## Context

During Session 37 publish flow (16,25), `19_publish_picks.py` crashed
with:

```
sqlite3.OperationalError: no such column: pitcher_id
```

The error originated at `validate_starter_data()` line 603, which
SELECTed `pitcher_id` from `bet_tracker`. Per SCHEMA.py, `bet_tracker`
has no `pitcher_id` column — only `pitcher_name`.

The validator has two code paths for props:
- `bet_tracker` source (K props): hard-coded `pitcher_id` in SELECT
- `outs_tracker` source: PRAGMA-checks for `pitcher_id` column,
  falls back to `NULL AS pitcher_id` if absent

The `outs_tracker` path was already defensive; the `bet_tracker`
path was not. The validator then required `pid is not None` to
pass, so even after fixing the SELECT, the validator would
reject every K prop because pitcher_id is unavailable.

This validator was added between Sessions 22 (last known clean K
publish) and Session 37. Exact session of introduction not
identified — neither HISTORY.py nor ROADMAP.py records the addition.
The bug was latent until Session 37 was the first session in which
the publish flow hit the validator with a K prop pick.

## Decision

Patch `validate_starter_data()` to:

1. Mirror the `outs_tracker` defensive PRAGMA pattern for the
   `bet_tracker` branch — schema-check before SELECT, fall back
   to `NULL AS pitcher_id` if column absent.
2. When `pid is None`, do not reject. Verify the pitcher exists
   in `daily_games` via `pitcher_name` match instead.

The patch preserves the validator's intent (confirm the pitcher
is in today's slate) while accommodating tables that legitimately
do not carry `pitcher_id`. The fallback path is equivalent in
strictness — name match is sufficient because `daily_games`
loads pitcher names from the same source as `bet_tracker`.

## Backup and rollback

Original file backed up to `19_publish_picks.py.bak_session37`
before patch application. Rollback path: copy backup to live name.

## Smoke test

Post-patch run of `19_publish_picks.py` on Session 37 publishable
candidates `16,17` (King K U 5.5, Detmers K U 6.5) confirmed
publish succeeded.

## Open hygiene items

- The validator change between Session 22 and Session 37 was
  not documented in HISTORY.py. Recommend a HISTORY check
  pattern: any change to `19_publish_picks.py` (publish-path
  script) gets a session entry.
- `bet_tracker` table does not store `pitcher_id` despite K props
  being pitcher-specific. The validator workaround is correct
  for now; the schema-level question of whether `bet_tracker`
  *should* carry `pitcher_id` is deferred. Pros: enables tighter
  joins for analysis. Cons: tracker is currently denormalized
  by design (single row, all consumer fields).

## Lessons

- **Schema discovery before SQL** rule (HISTORY.py Session 26)
  applies to *modifying* code too, not just writing new diagnostics.
- Code-path coverage gaps in the publish flow: the validator was
  never exercised by any K prop publish until Session 37. Untested
  paths in deployment scripts are P1 risk; future validator
  additions should ship with smoke tests that exercise all
  source_table branches.

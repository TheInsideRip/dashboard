# ADR-023: Outs pipeline team-swap bug — root cause and fix

Status: Accepted
Date: 2026-04-20
Session: 23
Supersedes: (partial) patches in fix_28i_outs_complete.py, fix_athletics_outs.py
            — both left root cause intact

## Context

`28i_outs_pipeline.py` is the outs-prop data pipeline. It pulls prop
lines from The Odds API, matches each pitcher to their team via
`daily_games`, and writes rows to `outs_tracker` with
`pitcher_team` and `opp_team`. The downstream tagger
`tag_outs_edges()` looks up each row's pitcher-team bullpen workload
to determine OUTS_UNDER_STRONG / OUTS_UNDER_ELITE eligibility.

On 2026-04-20 morning, Dylan Cease's 17.5 outs line failed to tag
OUTS_UNDER_STRONG despite TOR BP 228 ≤ P20 threshold 238, meeting
every filter condition on paper. Investigation revealed
`outs_tracker` had `pitcher_team='LAA'` (wrong) and `opp_team='TOR'`
(wrong). The tagger was looking up LAA's BP (not TOR's) and
correctly finding no qualification, because the wrong team was
stored.

Cross-tracker audit over 10 days of rows showed this was systematic:
~45% of outs_tracker rows had swapped team fields, ~8% had other
wrong values, only ~47% were correct. `totals_tracker`, `mlrl_tracker`,
`mlrl_streak_picks`, and `published_picks` were all 100% clean —
the bug was isolated to the outs pipeline.

### Root cause

`match_pitcher_to_team()` was executing a SQL WHERE against
`daily_games` using **full-name team strings** (e.g. "Los Angeles
Angels") passed in from The Odds API's event payload, while
`daily_games.home_team` stores **abbreviations** (e.g. "LAA"). The
query returned zero rows on every call.

When the match function returned None, the caller's fallback at
line 414-417 silently assigned:

    pitcher_team = home_team
    opp_team     = away_team

regardless of which team the pitcher actually played for. For
**home starters** this coincidentally stored the correct team. For
**away starters** it stored the wrong team — the home team's
abbreviation. Result: systematic ~50% field swap on away-starter
rows.

Two prior sessions had touched parts of this code without fixing it:

- `fix_28i_outs_complete.py` addressed resolver NULL guards,
  game_pk storage, void casing, and published_picks sync. Did not
  touch `match_pitcher_to_team` or the unsafe fallback.
- `fix_athletics_outs.py` explicitly acknowledged the fallback bug
  in its docstring, fixed 6 specific Athletics rows, and added
  `'Athletics': 'ATH'` to team_map. Did not fix the underlying
  match function or remove the fallback.

Both fixes were surface patches that addressed symptoms while
leaving the root cause (the query mismatch + unsafe fallback) intact.

## Decision

**Rewrite `match_pitcher_to_team()` to query `daily_games` by
`pitcher_name` directly** (last-name match with first-name
disambiguation for collisions), returning abbreviations as stored
in `daily_games`. **Remove the unsafe fallback entirely** — on match
failure, skip the row with a warning log rather than silently
storing wrong-but-shaped-correct data.

Backfill 143 historical rows in `outs_tracker` using the same logic,
preserving a full-table snapshot backup.

### Alternatives considered and rejected

**(a) Map full names → abbreviations before the SQL query.**
Would have preserved the existing call signature and fallback
structure. Rejected because it leaves the unsafe fallback in place
for future failure modes (e.g., a new team rename, a data-quality
issue in daily_games); the silent-lie pattern is the actual hazard,
not the specific full-name/abbrev mismatch.

**(b) Retroactively delete the 143 mis-assigned rows.**
Rejected because many rows had resolved results tied to them and
had been reconciled against MLB Stats API. Deleting would have
orphaned downstream references; backfilling the team fields
preserves the audit trail.

**(c) Leave historical rows alone, fix only forward.**
Rejected because the mis-assigned historical rows were skewing
edge-performance analysis. With the fix applied only forward, any
analysis of `OUTS_UNDER_STRONG` live performance would continue to
be biased by the 143 bad historical rows.

**(d) Substring last-name match (used in Phase A v1).**
Attempted and rejected after the Phase B dry-run surfaced
collisions: "Patrick" (Chad Patrick) matched "Patrick Corbin" via
first-name substring, "Martin" (Davis Martin) matched "Nick
Martinez" via last-name substring. Replaced with exact last-token
match + first-name disambiguation.

## Consequences

### Positive

- Outs pipeline now correctly identifies pitcher team for both
  home and away starters.
- 143 historical rows corrected in Phase B backfill (post-update
  verification: 0 SWAP, 0 OTHER, 287 OK, 20 UNMATCHABLE).
- Unsafe fallback removed; a future match failure will now be
  visible in logs rather than silently wrong in the tracker.
- Cease id=306 retroactively confirmed as would-tag OUTS_UNDER_STRONG.
- Edge-performance analysis now draws from correctly-classified data.

### Negative / Caveats

- Pre-patch live sample for OUTS_UNDER_STRONG was drawn entirely
  from home-starter rows (the subset the bug happened to assign
  correctly). That sample is a selection artifact, not a clean
  forward-looking estimate of edge performance. Forward expectation
  should anchor to the 58% backtest WR, not to pre-patch live WR.

- 20 rows remain UNMATCHABLE (pitcher not in daily_games for the
  logged date). Likely a mix of pre-scratch bet logs and name-format
  mismatches. Left alone by Phase B — deferred audit.

- Logic is duplicated between `28i_outs_pipeline.py` and the
  Phase B backfill script. Future change: extract to a shared
  `team_match.py` module.

- Backtest validation is NOT contaminated by this bug. Scripts
  28a-28h reconstruct pitcher→team mapping from `pitches_historical`
  each row, independent of `outs_tracker`. The 58% WR claim stands.

## Process lessons

1. **Silent fallbacks producing wrong-but-shaped-correct data are
   indistinguishable from working code until weeks later.** Any
   `if X is None: X = <safe-seeming default>` pattern needs a
   review: is the default actually safe for all downstream usage,
   or does it propagate silently? In this case a log+skip was the
   right answer; the fallback produced wrong data that went
   undetected for weeks.

2. **Surface patches that acknowledge a root cause in their
   docstring without fixing it create maintenance debt.**
   `fix_athletics_outs.py` explicitly called out the fallback bug
   but fixed only its symptom (6 Athletics rows). The docstring
   documentation without root-cause fix is worse than no fix:
   future readers assume the problem has been addressed.

3. **Substring matching on short names collides.** Exact token
   matching with disambiguation is the safer default. The Phase A
   v1 substring matcher was caught by the Phase B dry-run — script
   duplication meant the bug existed in two places simultaneously,
   and only catching it in one would have shipped a broken fix.

4. **When a data bug creates a selection artifact in live records,
   pre-patch live numbers are NOT a clean estimate of edge
   performance.** The pre-patch OUTS_UNDER_STRONG live sample was
   home-only. Do not average pre-patch with post-patch live as if
   they represent the same population. Default to backtest anchor
   until a clean post-patch forward sample accumulates.

## Implementation artifacts

Source changes (all reversible via .bak):
- `28i_outs_pipeline.py` — `match_pitcher_to_team()` rewritten;
  unsafe fallback removed. Sentinel: `# PATCHED 2026-04-20 v2:
  hardened name matching`

Scripts produced:
- `patch_28i_team_bug_phase_a.py` — initial source patch
- `patch_28i_team_bug_phase_a_hardened.py` — collision fix
- `backfill_outs_team_fields_phase_b.py` — historical backfill
- `report_missed_outs_phase_c.py` — read-only missed-picks report
- `verify_outs_fix_phase_d.py` — end-to-end verification

Database changes:
- 143 rows in `outs_tracker` updated
- New backup table: `outs_tracker_backup_team_fix_20260420_203320`
  (full 307-row snapshot pre-correction)

## Verification

Phase D verification passed all four checks:
1. Source sentinels present in `28i_outs_pipeline.py`
2. Unsafe fallback regex absent from source
3. `outs_tracker`: 0 SWAP, 0 OTHER, 287 OK, 20 UNMATCHABLE
4. Cease id=306 simulation correctly identifies would-tag STRONG

## References

- Phase C read-only report output (pasted in session transcript,
  2026-04-20 ~20:35 local)
- Phase D verification output (pasted in session transcript,
  2026-04-20 ~20:40 local)
- `RULES_FOR_CLAUDE.py` Pattern S1 (silent exception handlers) —
  this bug is a close cousin of that pattern
- `RULES_FOR_CLAUDE.py` Pattern S2 (NULL-unsafe SQL) — same class
  of silent-failure problem

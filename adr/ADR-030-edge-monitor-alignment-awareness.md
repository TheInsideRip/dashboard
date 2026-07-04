# ADR-030: edge_monitor.py alignment-date awareness — population mixing fix

Status: Accepted
Date: 2026-05-10
Session: 29

## Context

`edge_monitor.py` is the system's primary live-performance reporting
tool. For each tagged edge, it computes win rate, P&L, ROI, monthly
stability, streak status, and rolling 30 metrics by aggregating all
resolved tagged bets in the relevant tracker tables.

Until Session 29, edge_monitor had **no awareness of alignment events**
— ADR-023 (outs team-swap fix, 2026-04-20), ADR-024 (PARK_FACTORS
alignment, 2026-04-21), ADR-029 (SP fallback exclusion, 2026-05-10).
Each of these alignment events changed the population an edge fires
on. Pre-alignment and post-alignment picks for affected tags are
**different populations**, and aggregating them produces invalid
forward-inference numbers.

ADR-024 explicitly noted this hazard:

> "Pre-alignment and post-alignment live picks are different
> populations. Any aggregate 2026-to-date HIGH_PARK_GAP WR
> computation must either (i) segment pre/post 2026-04-21, or
> (ii) reset the forward sample to zero."

But edge_monitor did neither. It pulled all rows where
`clv_tag = 'HIGH_PARK_GAP' AND result_hit IS NOT NULL` and computed
aggregate stats on the union.

### Discovery

During Session 29's HIGH_PARK_GAP live-underperformance investigation
(item 3 on session followup list), Claude built
`diag_hpg_live_underperformance_h1_h2.py` to check whether the
"11W-13L (45.8%) live" gap edge_monitor reported was variance or
real degradation. The diagnostic queried `totals_tracker` filtered by
`clv_tag = 'HIGH_PARK_GAP' AND game_date >= '2026-04-21'` (post-
alignment) and found only 6 picks (3W-3L).

Reconciling: 8W-10L pre-alignment + 3W-3L post-alignment = 11W-13L
matches edge_monitor's number exactly. **edge_monitor was reporting
the union as if it were post-alignment data.** All decisions framed
on the 11W-13L number — the "underperformance" framing in Phase 3a's
documentation, the size of the forward demote sample, the inferred
gap vs backtest — were anchored to a mixed-population number.

A follow-up audit (`diag_edge_monitor_alignment_audit.py`) extended
the check to all 12 tagged edges. **8 of 12 tags had alignment
events that resulted in mixed-population numbers in edge_monitor.**
Only MLRL_STREAK_ELITE and the three K-prop edges have always been
clean.

### Affected tags and effective alignment dates

| Tag | Alignment date | Source |
|-----|---|---|
| HIGH_PARK_GAP | 2026-04-21 | ADR-024 PARK_FACTORS alignment |
| OUTS_UNDER_STRONG | 2026-04-20 | ADR-023 outs team-swap fix |
| OUTS_UNDER_ELITE | 2026-04-20 | ADR-023 outs team-swap fix |
| UNDER_VALIDATED | 2026-05-10 | ADR-029 SP fallback exclusion |
| UNDER_WEATHER_3 | 2026-05-10 | ADR-029 SP fallback exclusion |
| UNDER_WEATHER_2 | 2026-05-10 | ADR-029 SP fallback exclusion |
| UNDER_DOME | 2026-05-10 | ADR-029 SP fallback exclusion |
| UNDER_AVOID | 2026-05-10 | ADR-029 SP fallback exclusion |

### Mixed-vs-correct numbers as of 2026-05-10

| Tag | edge_monitor (mixed) | Correct post-alignment |
|-----|---|---|
| HIGH_PARK_GAP | 11W-13L (45.8%) | 3W-3L (50.0%, n=6) |
| OUTS_UNDER_STRONG | 14W-9L (60.9%) | 7W-6L (53.8%, n=13) |
| OUTS_UNDER_ELITE | 2W-1L (66.7%) | 2W-0L (n=2) |
| UNDER_VALIDATED | 4W-14L (22.2%) | (no post-alignment yet; today is alignment) |
| UNDER_WEATHER_3 | 6W-3L (66.7%) | (no post-alignment yet) |
| UNDER_WEATHER_2 | 4W-3L (57.1%) | (no post-alignment yet) |
| UNDER_DOME | 4W-2L (66.7%) | (no post-alignment yet) |
| UNDER_AVOID | 1W-2L (33.3%) | (no post-alignment yet) |

The most consequential discovery is **OUTS_UNDER_STRONG**: the
"beating backtest" framing in memory was based on a 60.9% mixed
number. The actual post-alignment performance is 53.8% (CI [29.1%,
76.8%]) — slightly below backtest 58%, with sample size too small
to draw conclusions.

### Decisions framed on mixed numbers (Session 29)

The following Session 29 decisions cited mixed-population live numbers
in their narrative framing:

- Phase 3a writeup: HIGH_PARK_GAP "Live: 11W-13L (45.8%)
  post-alignment" — incorrect attribution.
- ADR-029: UNDER_VALIDATED "Live 4W-14L (22.2%) is variance against
  a verified 57% edge" — the 4W-14L is pre-SP-fallback-fix; today's
  patch is the alignment.

The decisions themselves — Phase 3a gate-watch on HIGH_PARK_GAP, hold
lift on UNDER_VALIDATED — remain correct on independent grounds (v5a
substrate verification, residual subset 3/3 gates). Only the live-
record context in the narrative was misattributed.

## Decision

**Add alignment-date awareness to edge_monitor.py.**

### Code change

`edge_monitor.py` gains a top-level `ALIGNMENT_DATES` dict mapping
each tag to its effective post-alignment date (or `None` if no
alignment event applies). All display paths (brief, full, single-tag,
aggregate) split bets by alignment date when applicable:

- Pre-alignment record: shown labeled as "invalid for forward inference"
- Post-alignment record: shown with Wilson CI, used as the basis for
  alerts, streak detection, rolling 30, and backtest gap computation
- Aggregate "ALL TAGGED" line: shows both mixed total and
  forward-only total (post-alignment for affected tags + all clean
  tags)

Tags without alignment events display unchanged.

### Document corrections

Five documents had Session 29 entries citing mixed numbers:

- `ROADMAP.py` — HIGH_PARK_GAP edge block "Live: 11W-13L"
- `DECISIONS.py` — Session 29 entry HIGH_PARK_GAP and UNDER_VALIDATED
  live records
- `HISTORY.py` — Phase 17 entry HIGH_PARK_GAP live record
- `docs/adr/ADR-028-06a-outer-loop-bug.md` — Phase 3a status update
  HIGH_PARK_GAP record
- `docs/adr/ADR-029-22l-under-validated-restructure.md` —
  UNDER_VALIDATED "Live 4W-14L" framing

Each is corrected with surgical str_replace patches that preserve the
underlying decision logic and replace only the misleading
attribution. Patches deliver alongside this ADR.

### Alternatives considered

**(a) Leave edge_monitor as-is, add a manual override note to ROADMAP.**
Rejected. Pattern S6 ("aggregate-as-single-edge") is documented in
RULES_FOR_CLAUDE.py as a known recurring failure mode. Manual notes
do not prevent the next reader from being misled.

**(b) Reset all live-tracking to zero on alignment events
(physically delete pre-alignment data).** Rejected. Pre-alignment
data has historical value (audit trail, methodology lessons,
P&L accounting). Filtering at display time preserves the data while
correcting the framing.

**(c) Per-tag alignment dates as constants in edge_monitor only
(not in ADRs).** Rejected. ALIGNMENT_DATES is a reference table
with operational implications across multiple files. ADR-030 plus
the constant in edge_monitor jointly serve as the source of truth.
Future alignment events should add an ADR AND update ALIGNMENT_DATES.

## Consequences

### Positive

- edge_monitor reports both pre/post-alignment splits and a
  forward-only aggregate. Pattern S6 closed for tagged-edge reporting.
- Forward demote rules (e.g. HIGH_PARK_GAP "demote at n>=30 below
  55%") now use the correct sample.
- Methodology lesson: when a code patch changes the population an
  edge fires on (parker filter, fallback exclusion, threshold change),
  the corresponding ADR must register an alignment date in
  edge_monitor's `ALIGNMENT_DATES` dict.

### Negative / Caveats

- Hard-coded `ALIGNMENT_DATES` in edge_monitor is a maintenance
  point: future alignment events require updating both this ADR's
  table and the dict in code. Process discipline gap, not a bug.
- Existing live samples for UNDER_* edges show as "no post-alignment
  picks yet" until tagger fires post-2026-05-10. Expected; not an
  error.
- Operational finding (OUTS_UNDER_STRONG forward 53.8% vs memory's
  60.9%) is real but separate from this ADR. Logged for future
  investigation in ROADMAP "On the horizon".

### Pre-change vs post-change populations

For each affected tag:
- Pre-change: edge_monitor showed mixed pre+post aggregate.
- Post-change: edge_monitor shows pre and post separately, with
  forward-relevant computations (Wilson CI, alerts, rolling 30,
  streak) using post only.

Existing data is unchanged; only display/computation logic differs.

## Verification

### Pre-deployment

- `diag_edge_monitor_alignment_audit.py` (Session 29) confirmed the
  mixing pattern across 8 of 12 tagged edges. Output preserved in
  session transcript.
- `patch_edge_monitor_alignment_dates.py` tested end-to-end on a
  copy of edge_monitor.py: dry-run, apply, idempotency, post-write
  parse — all pass.
- Smoke test: ran patched edge_monitor against a synthetic in-memory
  database with mixed-alignment, no-alignment, and post-only-empty
  edge cases. Output displayed correctly in brief, full, and
  aggregate modes.
- Five Session 29 documentation patches independently tested.

### Post-deployment

- Post-pregame run: confirm edge_monitor output matches expected
  split format on real data.
- Forward HIGH_PARK_GAP demote-rule sample: count picks where
  `clv_tag = 'HIGH_PARK_GAP' AND game_date >= '2026-04-21'`, treat
  this n as the forward demote sample. Currently n=6 (vs the n=24
  implied by mixed framing).

## Forward monitoring

- Each future ADR that changes the population an existing tag fires
  on must register the alignment date in `ALIGNMENT_DATES`.
- Forward demote thresholds (per-edge, in ROADMAP) reference
  post-alignment n explicitly going forward.

## Follow-ups (not blocking)

- **OUTS_UNDER_STRONG operational review**: post-alignment 53.8% vs
  backtest 58% (n=13, CI [29.1%, 76.8%]) is variance-consistent but
  notably below memory's "beating backtest" framing. Worth a
  dedicated investigation when sample reaches n=20+ or as a side
  item in next session.
- **K_OVER_OPP_K edge_monitor reading**: 6W-8L (42.9%) on n=14 vs
  backtest 57% — gap is meaningful even at small n. Wilson CI lower
  bound below break-even. Worth its own investigation, separate from
  this ADR.
- **Unify edge_monitor BACKTEST_BENCHMARKS with ADR-aligned values**:
  edge_monitor still shows HIGH_PARK_GAP wr=73.8 (v4) and
  UNDER_VALIDATED wr=58.1 (v4 / 2-year). v5a numbers are 66.8 and
  57.0 respectively. Logged as a separate small patch.

## References

- `RULES_FOR_CLAUDE.py` Pattern S6 (aggregate-as-single-edge) —
  this ADR closes a specific instance.
- `docs/adr/ADR-023-outs-team-swap-root-cause.md` — alignment date
  2026-04-20 for OUTS_*.
- `docs/adr/ADR-024-park-factors-alignment.md` — alignment date
  2026-04-21 for HIGH_PARK_GAP. Explicitly warned about
  population-mixing risk; this ADR closes that warning.
- `docs/adr/ADR-029-22l-under-validated-restructure.md` —
  alignment date 2026-05-10 for UNDER_*.
- `diag_edge_monitor_alignment_audit.py` (Session 29 diagnostic).
- `patch_edge_monitor_alignment_dates.py` (Session 29 code patch).
- Session 29 doc-correction patches (5 files).

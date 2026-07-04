# ADR-024: PARK_FACTORS alignment between live tagger and research substrate

Status: Accepted
Date: 2026-04-21
Session: 24

## Context

`22l_tag_validated_edges.py` is the totals tagger. Its `HIGH_PARK_GAP`
rule is the strongest individual totals edge in the system (claimed
n=108, 69.9% WR across 2023-25 per verify_edges_v4). The tagger's
filter logic:

```python
HIGH_PARK_GAP_MIN = 1.3
HIGH_PARK_THRESHOLD = 1.05
PARK_FACTORS = { "COL": 1.278, "TEX": 1.091, ... }  # 30 teams

if gap >= HIGH_PARK_GAP_MIN and pf >= HIGH_PARK_THRESHOLD:
    tag = "HIGH_PARK_GAP"
```

where `pf = PARK_FACTORS.get(home, 1.0)` and
`gap = predicted_total - book_line`.

Live performance through 2026-04-20 was 8W-10L (44.4%), well below
the 73.8% two-year backtest claim. Wilson 95% CI [24.6%, 66.3%]
placed the upper bound below the claim — statistically inconsistent
with variance-only.

Investigation audited the tagger end-to-end. All 18 live rows
correctly matched the stated filter (gap ≥ 1.3, pf ≥ 1.05, direction
OVER). No tagger bug. The filter logic itself matched verify_edges_v4's
filter:

```
verify_edges_v4.py:
    "filter_sql": "(bt.predicted_total - ho.median_line) >= 1.3
                   AND bt.park_factor >= 1.05"
```

Both sources used identical gap threshold, park threshold, direction,
and computation. The only difference was **where the park_factor
value came from**:

- **Research (verify_edges_v4):** read `park_factor` from the
  `game_totals_backtest` database table.
- **Live tagger (22l):** read from the hardcoded Python constant
  `PARK_FACTORS = {...}` at the top of the file.

Those two sources disagreed on which parks qualified at ≥ 1.05.

### The disagreement

| Team | Hardcoded (live) | game_totals_backtest | Qualifies where? |
|------|------------------|----------------------|------------------|
| COL  | 1.278            | 1.278                | Both             |
| AZ   | 0.993            | 1.096                | **Research only** |
| BOS  | 1.062            | 1.060                | Both             |
| WSH  | 1.061            | 1.055                | Both             |
| TEX  | 1.091            | 0.957                | **Live only**     |
| CIN  | 1.085            | 1.032                | **Live only**     |
| DET  | 1.054            | 0.985                | **Live only**     |

Research-qualifying set: AZ, BOS, COL, WSH (4 parks).
Live-qualifying set: BOS, CIN, COL, DET, TEX, WSH (6 parks).
Overlap: 3 parks.

The hardcoded dict's inline comment read
`# Park factors (from game_totals_backtest / 10a model)` — implying
alignment that did not exist in reality. Origin of the specific
hardcoded values is not documented; they were either typed from an
earlier/different version of the table, sourced from an external
reference (FanGraphs, Baseball Reference, etc.), or updated
independently at some point.

### Consequences of the drift

**AZ was invisible to the live tagger.** Hypothetical 2023-25
backtest on AZ home games meeting the HIGH_PARK_GAP filter: n=63,
42W-21L (66.7% WR), +16.80u @ -110. Wilson 95% CI [54.4%, 77.1%]
— entire interval above break-even. Zero AZ picks published in
the 2026 season pre-alignment.

**CIN, DET, TEX fired live but were not in the research substrate.**
Combined hypothetical 2023-25 backtest: n=5, 3W-2L. Sample size
insufficient to confirm or refute edge existence at those parks.
2026 live exposure: 3 DET picks, 1W-2L, −1.00u.

**The 69.9% / 73.8% WR claims in ROADMAP.py referenced the research
population.** The live tagger was producing a different population
that independently validated (HC-substrate n=48, 72.9% WR, CI
[59.0%, 83.4%]) but was never the population the claim rested on.

The 2026-04 live underperformance (44.4%) vs the claim (73.8%)
cannot be cleanly attributed to drift alone — even restricted to
the 3 overlapping parks (BOS/COL/WSH), live was 7W-8L (46.7%) on
n=15, still well below backtest expectation. The residual gap is
most likely small-sample variance, potentially compounded by
early-season effects (HC-equivalent March-April backtest was
64.3% vs 72.9% full season). The alignment does not claim to
resolve the live underperformance; it resolves the population
mismatch so that forward comparisons are apples-to-apples.

## Decision

**Replace the hardcoded `PARK_FACTORS` dict in 22l with values
pulled directly from `game_totals_backtest.park_factor`.** After
replacement, the live tagger's HIGH_PARK_GAP rule fires on the
same park universe verify_edges_v4 verified.

Patch applied via `patch_align_park_factors.py` on 2026-04-21 at
12:27:56 local time. Pre-patch backup preserved at
`22l_tag_validated_edges.py.pre_pf_align_20260421_122756.bak`.

### Alternatives considered and rejected

**(a) Leave both sources and document the discrepancy only.**
Rejected. The live tagger produces picks that carry a validated-edge
badge ("HIGH_PARK_GAP: 73.8% WR") for games the research never
evaluated. This is a trust-the-system violation regardless of
whether either substrate is "correct." Alignment is the integrity
fix.

**(b) Re-run verify_edges_v4 against the hardcoded dict's park
universe and validate it as the authoritative substrate.** This
would preserve the live universe and align research to it. Rejected
because (i) AZ is meaningfully profitable and dropping it forfeits
edge, (ii) CIN/DET/TEX have n=5 of historical data and cannot be
meaningfully validated, (iii) the research substrate is the one
that passed formal 3-year triple verification and is referenced
throughout ROADMAP.py and DECISIONS.py.

**(c) Compute fresh park factors from 2023-25 actual game data
using a first-principles methodology (runs at park / league avg).**
Rejected as a blocker for alignment — the research substrate
already encodes some methodology (the `game_totals_backtest` table
was populated once with these values), and we should align to that
substrate today rather than re-derive. Re-derivation is a separate
methodology question deferred to a later session (see Follow-ups).

**(d) Add AZ to the hardcoded dict without removing CIN/DET/TEX.**
A partial alignment that preserves picks at drift parks. Rejected
because it leaves the substrate mismatch in place — we'd still be
firing on parks the research didn't evaluate, just adding one more
that it did.

## Consequences

### Positive

- Live tagger's HIGH_PARK_GAP now fires on exactly the 4 parks
  (AZ, BOS, COL, WSH) that verify_edges_v4 validated at 69.9%
  WR across 2023-25.
- AZ home games become visible to the tagger. Expected ~20
  qualifying picks per season based on 2023-25 historical rate.
- Claims cited in ROADMAP.py and DECISIONS.py now correctly
  reference the population the live tagger produces.
- Forward monitoring of HIGH_PARK_GAP live WR starts from a
  clean, research-aligned baseline.

### Negative / Caveats

- **Pre-alignment and post-alignment live picks are different
  populations.** Any aggregate 2026-to-date HIGH_PARK_GAP WR
  computation must either (i) segment pre/post 2026-04-21, or
  (ii) reset the forward sample to zero. The 18 pre-patch picks
  remain in `totals_tracker` as historical record but should not
  be combined with post-patch picks for edge performance analysis.

- **3 historical live picks at DET (1W-2L, -1.00u) were tagged
  on a substrate that is no longer considered a validated edge.**
  These resolve as-is; no retroactive voiding.

- **No live smoke test available at patch time.** 22l runs as part
  of pregame_pipeline.bat which had not yet executed for 2026-04-21.
  Structural test (import + qualifying-set check) confirmed the
  patched module loads correctly and qualifies ['AZ', 'BOS', 'COL',
  'WSH']. First operational test will be the 2026-04-21 evening
  pregame run.

- **Hardcoded-dict origin remains unknown.** We have aligned to
  the research substrate but have not identified why the hardcoded
  dict's values drifted in the first place. See Process lessons.

## Process lessons

1. **A comment claiming "sourced from X" is not evidence that a
   constant matches X.** The hardcoded `PARK_FACTORS` dict had an
   inline comment explicitly citing `game_totals_backtest / 10a
   model` as its source, but the values did not match. Any time
   a constant documents a source, a one-time verification script
   should exist to confirm (or be runnable on demand). Added to
   the standing watch list alongside Patterns S1-S6 in
   `RULES_FOR_CLAUDE.py`.

2. **The "44% vs 74%" live anomaly required three deepening
   passes before the root cause surfaced.** First pass: tagger
   audit (clean). Second pass: population clustering analysis
   (small-sample variance hypothesis). Third pass: substrate
   reconciliation (the drift). Without pushing past the
   "consistent with variance" stage, the drift would have
   remained in place indefinitely. The lesson is not "don't
   trust variance explanations" — most anomalies are variance —
   but "the investigation has to reach a root cause or an
   explicit sample-size pre-commitment before closing."

3. **Pre-committed action thresholds were useful discipline but
   not the mechanism that triggered this decision.** The
   thresholds for operational change (gap shift >0.3 runs,
   clustering <5% historical, etc.) did not all trip. The
   alignment was driven by a structurally clear misalignment
   discovered during the investigation, not by a threshold
   crossing. Both mechanisms have their place: thresholds guard
   against overreaction to small samples; structural findings
   justify action regardless of sample size.

4. **The readout "both park universes independently validate as
   edges" initially sounded reassuring but actually described
   the problem.** Two different validated edges should not exist
   for one claimed edge. The word "independently" was the tell
   — if they were the same edge, they would share a substrate
   by construction.

## Implementation artifacts

Source changes (reversible via .bak):
- `22l_tag_validated_edges.py` — `PARK_FACTORS` dict replaced.
  Header comment updated to reference this ADR.
  Backup: `22l_tag_validated_edges.py.pre_pf_align_20260421_122756.bak`

Scripts produced (all read-only, preserved in `E:\mlb_model`):
- `audit_high_park_gap.py` — v1 filter audit (had schema bug)
- `audit_high_park_gap_v2.py` — v2 with schema discovery
- `audit_high_park_gap_v3.py` — v3 with Wilson CI + series analysis
- `audit_high_park_gap_series_backtest.py` — v1 backtest clustering
- `audit_high_park_gap_series_backtest_v2.py` — v2 proper JOIN
- `probe_historical_odds.py` — schema discovery helper
- `investigate_high_park_gap_population.py` — v1 population
  analysis (had bugs)
- `investigate_high_park_gap_population_v2.py` — v2 (Stage 5 bug)
- `investigate_high_park_gap_population_v3.py` — v3 clean; surfaced
  the substrate drift
- `audit_park_drift.py` — AZ/CIN/DET/TEX segmentation
- `step1_diff_and_pull.py` — filter-logic diff + replacement dict
- `patch_align_park_factors.py` — the alignment patch

Database changes: none. `game_totals_backtest.park_factor` was
already the authoritative source; only the live tagger's hardcoded
constant was updated.

## Verification

Structural test post-patch (from loaded patched module):

```
Qualifying parks: ['AZ', 'BOS', 'COL', 'WSH']
Total teams: 30
```

Matches verify_edges_v4 qualifying set exactly. Python syntax
validated via `ast.parse` before write, after write in memory,
and after write from disk.

Operational verification pending the first 2026-04-21 pregame
pipeline run.

## Forward monitoring

Pre-alignment and post-alignment HIGH_PARK_GAP picks are different
populations. Forward performance tracking should start from
2026-04-21 on the aligned substrate, not aggregate pre/post.

A post-alignment live sample of n ≥ 30 is the threshold before
drawing inferences about whether live WR matches the 69.9%
research claim. At smaller samples, Wilson CI remains wide enough
to span backtest expectation.

## Follow-ups (not blocking)

- Document the origin and methodology of
  `game_totals_backtest.park_factor` values. They are consistent
  per team (one unique value per home team across 243 games),
  indicating they are lookup constants, not game-computed values.
  Identify which script populated them, which source years were
  used, and what formula was applied. This enables principled
  updates when the backtest table is next rebuilt.

- Audit other hardcoded constants in the codebase for potential
  similar drift from stated sources. Specific candidates:
  - `UNDER_GAP_MIN` / `UNDER_GAP_MAX` thresholds in 22l
  - Tier performance thresholds in `18_generate_dashboard.py`
  - BP percentile thresholds in `29a_mlrl_bp_tagger.py` (disabled
    but retained in source)

- Consider replacing the hardcoded dict with a direct DB read in
  22l (`SELECT home_team, park_factor FROM game_totals_backtest
  GROUP BY home_team`) to eliminate the possibility of future
  drift. Trade-off: adds a DB dependency to what is currently a
  fast in-memory lookup. Deferred as a non-urgent cleanup.

## References

- `RULES_FOR_CLAUDE.py` Rule P3 (validated filters are binding) —
  this patch satisfies the rule by aligning live to the verified
  substrate.
- `RULES_FOR_CLAUDE.py` Pattern S-series (silent failure modes) —
  the stale comment pattern ("sourced from X" not matching X)
  is a new failure mode worth adding as Pattern S7.
- `DECISIONS.py` "CLV ANALYSIS CONCLUSIONS (April 6, 2026 —
  Phase 6c)" — original HIGH_PARK_GAP discovery
- `HISTORY.py` Phase 10 Session 19 — verify_edges_v4 3-year
  verification results
- Investigation chain and patch output preserved in session
  transcript, 2026-04-21 ~08:00-12:30 local time.

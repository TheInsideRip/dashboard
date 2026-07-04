# ADR-033: 03c starter-identification row-order bug — bullpen_workload substrate

Status: Accepted
Date: 2026-05-17
Session: 33
Supersedes: (scope expansion of) original ADR-033 audit charter
            ("28i_outs_pipeline.py audit") per ROADMAP Session 32 priority #1

## Context

Session 32 (DECISIONS D4) placed OUTS_UNDER_STRONG on manual hold pending
audit. The audit was scoped to read `28i_outs_pipeline.py` end-to-end and
verify it against the backtest that produced its 58% WR / 64.5% WR claims.
Estimated scope: 1-2 sessions.

The audit completed structural review of 28i and **confirmed the tagger
logic matches the documented backtest filter spec** (UNDER + line >= 17.5
+ pitcher's-own-team bp_pitches_prior_3d <= P20). 28i is not the bug.

The audit then descended into the data substrate the tagger reads, and
surfaced a foundational defect: the `bullpen_workload` table — the
source-of-truth for `bp_pitches_today` and `bp_pitches_prior_3d` across
every bullpen-dependent edge — is populated by `03c_team_aggregations.py`
using a starter-identification step that depends on SQLite storage order
of `pitches_historical`. That order is not chronologically reliable,
and empirically appears reverse-chronological-per-game in the test cases
sampled.

### Root cause

`03c_team_aggregations.py`:

Line 76, the SELECT against `pitches_historical`:
```sql
SELECT ... FROM pitches_historical WHERE game_type = 'R'
```
No `ORDER BY`. SQLite returns rows in unspecified storage order.

The SELECT also does NOT include `pitch_number` in its column list
(line 64). So the DataFrame loaded into pandas has no canonical
chronological ordering key beyond `(inning, at_bat_number)` — and is
never sorted.

Line 129, starter detection:
```python
game_first_pitcher = df.groupby(["game_pk", "pitch_team"]).agg(
    first_pitcher=("pitcher", "first")
).reset_index()
```

`pandas.DataFrameGroupBy.agg("first")` returns the first non-null value
per group **in row iteration order**, which equals SQLite's storage
order for this query. The "first pitcher" is therefore "whichever
pitcher's row happened to appear first in the result set," not the
pitcher who threw the actual first pitch of the team's defensive half.

Line 139:
```python
df["is_starter"] = (df["pitcher"] == df["first_pitcher"]).astype(int)
df["is_reliever"] = 1 - df["is_starter"]
```

Every pitch by the actual starter — if they are not the "storage first
pitcher" for that (game_pk, pitch_team) — is misclassified as a
reliever pitch. The starter's pitches (typically 80-100 per game) are
then summed into `bp_pitches_today` at line 405:
```python
"bp_pitches_today": row["bp_pitches"],
"bp_pitches_prior_3d": prior["bp_pitches"].sum(),
```

### Evidence

`diag_adr033_d_03c_row_order_confirmation.py` (Session 33, read-only).
Three test cases drawn from `diag_adr033_c2v2_03c_exact_definition.py`'s
mismatch sample:

| Game | Storage starter (03c) | Actual starter (chronological) | bp_pitches storage / chrono / bullpen_workload |
|------|----------------------|--------------------------------|------------------------------------------------|
| DET 2024-06-09 (gpk 746463) | Englert (16p, inn 9) | Skubal (95p, inn 1) | 107 / 28 / **107 ✓** |
| ATH 2024-06-14 (gpk 745892) | Alexander (5p, inn 10) | Spence (83p, inn 1) | 134 / 56 / **134 ✓** |
| STL 2024-06-01 (gpk 745575) | Loutos (20p, inn 8) | Gray (86p, inn 1) | 116 / 50 / **116 ✓** |

3 of 3 test cases:
- 03c picked the wrong starter (pulled from inning 8/9/10, not inning 1).
- The "storage first" pitcher consistently came from a LATE inning,
  suggesting `pitches_historical` storage order is empirically
  reverse-chronological per game-team.
- `bp_pitches_today` under the storage-broken definition EXACTLY
  matches `bullpen_workload.bp_pitches_today`, confirming 03c is the
  source of the value.
- Actual bullpen pitches (under chronological definition) were 28, 56, 50.
- Inflation multiplier ranged 2.32x to 3.82x in the sample.

Pre-Session-33 sanity check from `diag_adr033_c2v2_03c_exact_definition.py`:
5 of 5 random June 2024 (team, date) pairs mismatched between
chronological reconstruction and `bullpen_workload`. Sample is too
small to estimate the affected-fraction population-wide, but the rate
is non-trivial.

### Cascade

Every consumer of `bp_pitches_today` or `bp_pitches_prior_3d` reads a
metric that drastically over-counts on an unknown fraction of games:

| Consumer | What it does with the metric |
|----------|------------------------------|
| `bullpen_workload` table | Source-of-truth column. Inflated. |
| `bullpen_stats` table | Aggregates over reliever rows tagged by 03c. Likely inflated similarly. |
| `game_context` (populated by 05c) | Reads `bullpen_workload` via JOIN. Inherits inflation. ADR-031 fixed *staleness* of these reads, not underlying metric correctness. |
| `populate_today_bp_workload.py` | Sums `bp_pitches_today` over the prior-3d window. Inflated. |
| `28i_outs_pipeline.py` | Reads `game_context.{home,away}_bp_pitches_prior_3d` for tagging AND `_compute_rolling_bp_p20()`. Both inflated. |
| `29a_mlrl_bp_tagger.py` | Reads `game_context.home_bp_pitches_prior_3d` for ML_BP_EXHAUST_STRONG / ELITE. Inflated. |
| `22l_tag_validated_edges.py` | Indirectly via `game_context`. Effect on UNDER tags is via P75/P90 thresholds in 03c's flag derivation. |
| `26e_mlrl_tagger.py` | Streak features; may consume `bp_workload_flag`. Confirm. |
| OUTS_UNDER_STRONG/ELITE 698-game backtest (n=124) | Measured in the broken-metric space. |
| ML_BP_EXHAUST 998-game backtest (n=1,192) | Same broken-metric space (per Session 19 work). |

The validated edges (58% / 64.5% / 56.2%) are **self-consistent within
the broken-metric space** — backtest and live both use the same broken
metric. The edges may still be real. They cannot, however, be
interpreted as "edge derived from real bullpen exhaustion" — they are
"edge derived from a peculiar function of team pitch totals minus one
arbitrarily-selected pitcher's contribution."

## Decision

Treat this as a substrate rebuild on the pattern established by ADR-028
(06a outer-loop bug). Multi-phase, read-only diagnostics first,
side-by-side v2 build second, re-validation third, cutover last.

**Operational status, immediate:**

1. OUTS_UNDER_STRONG remains on manual hold (DECISIONS Session 32 D4).
   This audit's findings deepen the rationale for the hold; they do
   not relax it.
2. OUTS_UNDER_ELITE remains on manual hold per the existing
   "unvalidated live" framing (Session 25 RED TEAM NOTE).
3. **NEW:** ML_BP_EXHAUST_STRONG and ML_BP_EXHAUST_ELITE (tags fired
   by `29a_mlrl_bp_tagger.py`) move to manual hold. Same substrate.
   Same broken-metric. No mechanism to argue the 56.2% / 59% WR
   numbers are interpretable without re-validation on v2 substrate.
4. UNDER_VALIDATED / UNDER_WEATHER_* tags remain on their existing
   holds and hold-status (per ADR-029, Session 32). 22l consumption
   of BP features is indirect; impact unknown until substrate v2 is
   built and re-verified.
5. The substrate-poisoning window per Session 32 D3 (2026-04-04 to
   2026-05-17) is **superseded** by a longer window: the entire
   history of `bullpen_workload` is suspect, not just 2026-04-04
   onward. Pre-window WRs that already had reduced status now have
   further reduced status. No backfill of forward records; this is
   the same pattern as Session 32's no-backfill decision.

**Multi-phase plan:**

- **Phase 1 — Quantification (1 session, read-only).**
  Compute fraction of (game_pk, pitch_team) pairs where 03c's
  storage-first pitcher differs from the chronological-first pitcher,
  across 2023-2025. Stratify by year. If <10% of pairs are
  misclassified, the impact may be small enough to handle with a
  targeted re-validation; if >50%, the metric is broken in a way
  that fundamentally changes interpretation.

- **Phase 2 — Build 03c_v2 + bullpen_workload_v2 (1 session).**
  Source patch to 03c: either (a) add `ORDER BY game_pk, inning,
  at_bat_number, pitch_number` to the SELECT (requires adding
  `pitch_number` to column list) and sort `df` after load; or (b)
  replace the `.agg("first")` starter detection with an explicit
  `idxmin` on `(inning, at_bat_number, pitch_number)`. Side-by-side
  table: `bullpen_workload_v2`. Verify byte-for-byte invariants
  (e.g. sum of starter + reliever pitches per game = total team
  pitches; bp_pitches_today <= total team pitches per (team, date)).

- **Phase 3 — Re-validate every BP-dependent edge (2 sessions).**
  OUTS_UNDER_STRONG, OUTS_UNDER_ELITE, ML_BP_EXHAUST_STRONG,
  ML_BP_EXHAUST_ELITE, and any UNDER tag that reads BP features.
  Triple verification on v2 substrate.

- **Phase 4 — Cutover (1 session).**
  Replace canonical `bullpen_workload` with v2. Archive v1 as
  `bullpen_workload_pre_fix_<date>`. Update 03c source. Update
  thresholds in 28i and 29a if any qualifying ranges shifted.

- **Phase 5 — Document (0.5 session).**
  Update ROADMAP / DECISIONS / HISTORY / SCHEMA gotchas. Add row-
  order pattern to RULES_FOR_CLAUDE.py SYSTEMIC PATTERNS section.

Estimated total: 5-6 sessions, plus Phase 1 surfacing potentially
further scope.

## Alternatives considered and rejected

**(a) Patch 03c, regenerate bullpen_workload in place, accept that
all prior validated edges may drift.**
Rejected. Every claimed BP-related edge becomes unverified
overnight. Same trust-the-system violation ADR-024 and ADR-028
fixed.

**(b) Leave the bug in place. The backtest and live are
self-consistent in the broken-metric space, so the edges are
empirically real even if the metric is mis-named.**
Rejected on two grounds. First, intellectual honesty: a model
that depends on a metric whose name does not match its meaning is
brittle (any future maintainer who reads "bp_pitches_today" will
assume it means bullpen pitches, and reasoning built on that
assumption will be wrong). Second, future-proofing: if the storage
order in `pitches_historical` changes (e.g., a future bulk reload
that inserts in chronological order), the metric definition
silently changes and every validated edge becomes invalid without
warning.

**(c) Fix 03c but leave bullpen_workload alone, only regenerate on
the next scheduled 03c run.**
Rejected. Live and historical would have different metric
definitions for a transition period. Same population-mixing
problem as ADR-024 / ADR-029.

**(d) Lift the OUTS_UNDER_STRONG hold today.**
Rejected. n=5 strict-aligned picks on the post-ADR-023 clean
window (2W-3L, 40% WR) provide no useful signal either direction,
and now the underlying metric is questioned at a deeper level.
Hold continues.

## Consequences

### Positive
- Substrate correctness restored on a foundation column used by
  multiple validated edges.
- Re-validation produces interpretable results: bp_pitches_today
  will actually mean bullpen pitches.
- 03c's storage-order assumption removed; metric becomes robust
  to changes in `pitches_historical` insertion order.

### Negative / Caveats
- Multi-session work blocking forward use of OUTS_UNDER_STRONG,
  OUTS_UNDER_ELITE, ML_BP_EXHAUST_STRONG, ML_BP_EXHAUST_ELITE.
- Some currently-claimed edge stats will not survive re-validation
  on the corrected substrate. Demotions expected.
- Pre-rebuild and post-rebuild tracked bets are different
  populations. Aggregate live comparisons across the cutover are
  invalid (same caveat pattern as ADR-024, ADR-028, ADR-031).
- Phase 1 may surface additional secondary findings (e.g.,
  `bullpen_stats` season-level metrics also affected) that expand
  scope further.

## Today's operational implications (2026-05-17)

- OUTS_UNDER_STRONG: hold continues (DECISIONS Session 32 D4 reinforced).
- OUTS_UNDER_ELITE: hold continues (Session 25 RED TEAM NOTE).
- ML_BP_EXHAUST_STRONG / ELITE: NEW HOLD. Tagger fires but tags
  should not be published until v2 substrate exists and re-validation
  completes.
- All other edges: status quo. 22l/26e/27i BP feature consumption is
  indirect, impact uncertain until Phase 1 quantifies.
- No code changes to production scripts today. Holds are operational,
  not in-tagger.

## Implementation artifacts

Scripts produced this session (all read-only, in `E:\mlb_model`):
- `diag_adr033_a_p20_alignment_audit.py` — initial A1 audit (queried
  wrong table, game_context; corrected by A3)
- `diag_adr033_a2_preflight.py` — schema + row-count preflight
- `diag_adr033_a3_bullpen_workload_audit.py` — backtest P20 from
  `bullpen_workload`, divergence vs game_context, slice analysis
- `diag_adr033_bc_divergence_and_baz.py` — gc vs bw divergence by
  date window, Shane Baz tag inspection
- `diag_adr033_c2v2_03c_exact_definition.py` — sanity check on
  stable 2024 history (5/5 mismatch)
- `diag_adr033_d_03c_row_order_confirmation.py` — 3/3 confirmation
  of the row-order hypothesis

Source files reviewed (not modified):
- `28i_outs_pipeline.py` — production tagger
- `populate_today_bp_workload.py` — today's-row writer (used the
  `bullpen_workload` definition)
- `03c_team_aggregations.py` — bullpen_workload populator (defect site)

No database writes. No source patches. ADR-033 is a documentation
and operational-hold deliverable; remediation begins in Phase 1 of
a future session.

## References

- `RULES_FOR_CLAUDE.py` Pattern S4 (hardcoded thresholds going stale)
  — related-class problem; metric-definition staleness vs threshold
  staleness.
- `RULES_FOR_CLAUDE.py` Pattern S6 (silent-fallback / aggregate
  misread) — same family: production code reads a value that means
  something different from what its name suggests.
- ADR-023 — outs pipeline team-swap (selection-artifact lesson:
  pre-fix and post-fix live numbers are different populations).
- ADR-024 — park factors alignment (live-vs-backtest spec drift).
- ADR-028 — 06a outer-loop bug (multi-phase substrate rebuild
  precedent).
- ADR-029 — 22l UNDER_VALIDATED restructure (filter mismatch
  precedent).
- ADR-031 — 05c BP staleness fallback (proximate predecessor;
  fixed STALENESS but did not surface the underlying metric defect
  audited here).
- ADR-032 — season hardcode bug (proximate predecessor; same
  category of "substrate is poisoned, no backfill, forward-track
  reset" decision).

## Process lessons (Session 33)

1. **The original audit charter was correctly scoped but
   incorrectly limited.** ADR-033 was scoped as "audit 28i,
   determine whether OUTS_UNDER_STRONG is real." The audit
   reached the answer "28i is correct relative to its inputs,"
   then could have stopped. Continuing to audit the *inputs* —
   which Session 32's audit charter did not require — was the
   step that surfaced the actual defect. Future audits scoped
   at "audit X" should explicitly include "audit X's inputs"
   when X's inputs are derived data.

2. **`.agg("first")` on a non-deterministic-ordering source is
   a code smell.** Any pandas operation that reduces a group to
   a single value via positional selection ("first", "last",
   `.iloc[0]`) where the source is loaded without ORDER BY
   should be flagged in code review. The pattern recurs (see
   ADR-028's `identify_starter_games` secondary bug: same shape,
   `.iloc[0]` after sort by `pitch_number` alone with
   non-deterministic tiebreak).

3. **A confirmation that a tagger "matches the spec" is not a
   confirmation that the spec is correct.** ADR-033 originally
   concluded 28i matched its filter spec. That was true. It was
   also irrelevant to whether the underlying metric was
   well-defined. Audits should distinguish "code matches spec"
   from "spec matches reality."

4. **Documented mistakes recur.** Session 25 superseded a
   diagnostic that used pitches_historical as a BP source
   ("table is refreshed weekly Monday; intra-week games never
   appear"). Session 33's reconstruction independently
   reproduced this same mistake on the same table, despite the
   note being in HISTORY.py. Mitigation: pre-flight checks on
   any pitches_historical-based reconstruction should query
   `MAX(game_date)` and flag if the requested window extends
   past it.

5. **The retraction of Finding 2 (Shane Baz tag) two turns
   before the actual root cause was a near-miss.** Had I let
   the false-positive Slice C finding stand and escalated it
   to operational action ("the tagger has a bug, patch 28i to
   tighten its threshold check"), the patch would have been
   wrong and the actual root cause would have been masked.
   PJK's enforcement of "verify, do not anchor on prior
   framing" (rules #6, #9, #15) was the discipline that
   produced the retraction in time.


## Phase 1 + Phase 2 status update — 2026-05-17 evening

Phase 1 and Phase 2 completed in a single continuation session
following the original ADR-033 charter.

### Phase 1 — Quantification complete

`diag_adr033_phase1_quantification.py` ran a population-scale audit
of (game_pk, pitch_team) pairs across 2023-2025 regular-season
pitches_historical data.

| Year | Pairs  | Match | Mismatch | % mismatch |
|------|-------:|------:|---------:|-----------:|
| 2023 | 4,860  | 35    | 4,825    | 99.28% |
| 2024 | 4,850  | 28    | 4,822    | 99.42% |
| 2025 | 4,856  | 29    | 4,827    | 99.40% |
| ALL  | 14,566 | 92    | 14,474   | **99.37%** |

Per Phase 2 scope decision in this ADR: >50% mismatch triggers full
bullpen_workload_v2 rebuild. Confirmed.

Distributional findings on mismatched pairs:
- Mean chrono-starter pitches mis-classified as relief: 85 (median 89)
- Mean inflation ratio bp_pitches_today (broken / real): 2.45x
- Max inflation ratio: 58x (2025-06-18 ATL game: real bp=2, broken=116)
- 57% of storage-first "starters" appear first in inning 9; 26% in inning 8
  -> confirms reverse-chronological storage order hypothesis at scale
- 92 matched pairs are all 1-pitcher complete games (tautological matches)

### Phase 1 — Red-team verification (3 independent checks)

`diag_adr033_phase1_redteam.py` triangulated the 99.4% claim:

1. **Storage-broken bp value matches bullpen_workload row-for-row:**
   99/100 random pairs. Confirms (a) the replication of 03c logic
   is correct and (b) bullpen_workload in the DB stores the broken
   metric.

2. **Chronological-first pitcher matches `daily_games` starter ID:**
   96/100 on 2026 sample (daily_games is populated only for 2026).
   Storage-first matched 0/100. Independent source-of-truth
   confirmation that the chrono path is correct.

3. **The 92 "matched" pairs are 1-pitcher complete games:** 100% of
   them. Tautological matches, fully explained.

All three checks passed. The 99.4% number is no longer a hypothesis.

### Phase 2 — Side-by-side v2 build complete

`03c_team_aggregations_v2.py` built `bullpen_workload_v2`,
`bullpen_stats_v2`, and `team_defense_v2`. Source 03c and v1 tables
untouched.

Three source-level changes (option 2a from the design discussion):
1. `pitch_number` added to SELECT column list
2. `ORDER BY game_pk, inning, at_bat_number, pitch_number` added to SELECT
3. Stable mergesort on the same key after pandas load
   (belt-and-suspenders against any future ETL change)

All downstream logic unchanged — same `.agg("first")` call site, but
now operating on a deterministically-sorted DataFrame.

**Sanity gate**: starter pitch share went from ~16% (broken) to 57.9%
(correct). Expected band 50-75%. PASSED.

**Invariants (all PASSED before write):**
- bp_pitches_today >= 0
- bp_pitches_today <= total_team_pitches
- starter_pitches + reliever_pitches == total_team_pitches
- (team, game_date) unique

**Distribution shift (v1 -> v2, joined 15,647 rows):**

| Metric (bp_pitches_prior_3d) | v1 | v2 | Δ |
|------------------------------|---:|---:|--:|
| mean   | 328.5 | 158.2 | -170.3 |
| P20    | 253   | 110   | -143 |
| P75    | 393   | 195   | -198 |
| P90    | 426   | 234   | -192 |

The metric was inflated by ~2.1x on average. P20 (the threshold
OUTS_UNDER_STRONG keys off) moved from 253 to 110 — a different
qualifying universe entirely.

### Scope expansion finding — bullpen_stats also poisoned

While reading 03c source for the v2 builder, observed that
`rel_df = df[df["is_reliever"] == 1]` (L246) is the input to BOTH
`bullpen_workload` (L374) AND `bullpen_stats` (L337). The bug
contaminates season-level bullpen quality metrics, not just daily
workload.

`diag_adr033_bullpen_stats_v1_vs_v2.py` quantified the season-level
deltas across 120 (team, season) rows:

| Metric | v1 mean | v2 mean | Δ | Max abs Δ per row |
|--------|--------:|--------:|--:|------------------:|
| bp_xfip          | 4.15  | 4.39  | +0.24  | 0.83 |
| bp_xwoba_allowed | 0.321 | 0.312 | -0.009 | 0.045 |
| bp_k_pct         | 0.222 | 0.231 | +0.008 | 0.045 |
| bp_whiff_rate    | 0.252 | 0.265 | +0.013 | n/a  |
| bp_avg_velo      | 89.2  | 89.7  | +0.5   | n/a  |

The sign pattern is consistent with what removing starter-pitches
from the bullpen pool would produce: real bullpens are higher-K,
higher-whiff, lower-xwOBA, higher-velocity than the v1 mix.

### Consumer audit — 12 production scripts read shifted columns

`diag_adr033_bullpen_stats_consumers.py` greped across 377 .py files.
12 production scripts read columns that shifted v1->v2:
05c (pipeline), 11 and 11b (live model serve paths), 10a
(training substrate), 03d, 28i, 22g, 26a, 28c-28h, and one study
script.

Critically: `11_predict_totals.py` reads `bp_xwoba_allowed`,
`bp_xfip`, `bp_fip`, `bp_k_pct` to produce live predicted_totals.
This means the totals model itself was operating on broken inputs
both at train time (10a) and at serve time (11). The model-mediated
edges (UNDER_WEATHER_*, UNDER_VALIDATED, HIGH_PARK_GAP) read those
predicted totals.

### Model impact study — predicted_total delta

`diag_adr033_bp_substrate_impact.py` swapped BP substrate (v1 vs v2)
in 10a's bullpen run-rate computation while holding all other
inputs constant. Used `game_totals_backtest_v2` (n=7,841) as baseline.

Caveat: `matchup_run_rate` reconstructed from log5 approximation
(10a's exact formula not read end-to-end). Direction is correct;
magnitudes approximate within ~20%.

| Metric (predicted_total delta v2 - v1) | Value |
|----------------------------------------|------:|
| mean                                   | -0.10 |
| median                                 | -0.10 |
| P5 / P95                               | -0.22 / 0.00 |
| min / max                              | -0.45 / +0.16 |

**Direction: systematically negative.** v2 predicts lower run totals
because v2 bullpens look better than v1's contaminated pool.

**Edge qualification flips:**

| Edge | v1 qualifies | v2 qualifies | Lost | New | Net |
|------|-------------:|-------------:|-----:|----:|----:|
| UNDER_VALIDATED | 1,302 | 1,571 | 100 | 369 | +269 |
| UNDER_WEATHER   | 1,583 | 1,946 | 6   | 369 | +363 |
| HIGH_PARK_GAP   | 456   | 364   | 92  | 0   | -92  |

The flipped games are not subsets. The v2 qualifying universe is a
different population than v1, not a stricter/looser filter on the
same games.

### Phase 3 scope, revised

Original ADR-033 Phase 3 envisioned re-validating workload-direct
edges (OUTS_UNDER family, ML_BP_EXHAUST family). The bullpen_stats
consumer audit and bp_substrate_impact study together establish
that the model-mediated totals edges (UNDER_*, HIGH_PARK_GAP) also
need re-validation — bigger lift than originally scoped.

Per DECISIONS Session 33 D7/D10, Phase 3 sequence is:

1. **Workload-direct first** (single session each):
   - OUTS_UNDER_STRONG vs bullpen_workload_v2
   - OUTS_UNDER_ELITE vs bullpen_workload_v2
   - ML_BP_EXHAUST_STRONG / ELITE vs bullpen_workload_v2

2. **Model-mediated second** (multi-session):
   - Build 10a_v3 (reads bullpen_stats_v2 + pitcher_cumulative_v2)
   - Produce game_totals_backtest_v3
   - MAE/bias check vs actual_total
   - verify_edges_v* against game_totals_backtest_v3 for UNDER_*,
     HIGH_PARK_GAP

### Operational holds — updated

**New hold this phase:**
- **HIGH_PARK_GAP** (DECISIONS D6): 20% of qualifying games disappear
  under v2; the lost games are systematically over-fired under v1's
  positive bias. Tagger continues to fire — do not publish until
  Phase 3 re-validation completes on game_totals_backtest_v3.

**Live during Phase 3 (DECISIONS D8, D9):**
- UNDER_WEATHER_2, UNDER_WEATHER_3 — under v2 they fire MORE picks,
  not fewer. Holding would forfeit identifiable forward picks for no
  risk-mitigation benefit (missed-opportunity, not downside-risk).
- MLRL_STREAK_ELITE — book-priced ML + game-results streak, no BP
  reads. Verified by consumer audit.
- K_OVER_OPP_K, K_OVER_WHIFF_VULN, K_UNDER_WHIFF_CONTACT — pitcher-
  level and lineup features only, no team-bullpen reads.

**Unchanged holds:**
- OUTS_UNDER_STRONG / ELITE (Session 32 D4 + Session 33 D1)
- ML_BP_EXHAUST_STRONG / ELITE (Session 33 D1)
- UNDER_VALIDATED (ADR-029, separate rationale)

### Artifacts produced this phase

Diagnostics (all read-only, retained as audit trail):
- `diag_adr033_phase1_quantification.py`
- `diag_adr033_phase1_redteam.py`
- `diag_adr033_bullpen_stats_v1_vs_v2.py`
- `diag_adr033_bullpen_stats_consumers.py`
- `diag_adr033_bp_substrate_impact.py`

V2 builder (writes _v2 tables only, source 03c untouched):
- `03c_team_aggregations_v2.py`

**Source 03c not patched. v1 tables not modified. Daily pipeline
unchanged.** All operational change is documentation + holds.

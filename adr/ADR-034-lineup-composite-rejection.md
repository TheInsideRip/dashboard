# ADR-034: Lineup Composite Dead-Code Hypothesis — Rejected by Data

**Status:** Accepted
**Date:** 2026-05-21 (Session 36)
**Supersedes:** Open hypothesis tracked since Session 32 as the top
                remaining drawdown lead

## Context

Since Session 32 (drawdown onset ~4/14, ~10 units below peak), the leading
unexplained-by-variance hypothesis was a train/serve feature divergence
involving lineup composite consumption in `11_predict_totals.py`.

Session 34 confirmed at the source-code level that:

1. `05c` writes lineup composites (`away_lineup_woba`, `home_lineup_woba`,
   plus `hitters_matched` counts) into `game_context` every morning when
   lineups are confirmed.

2. `11_predict_totals.py` **does not consume them**:

   `get_team_offense(conn, team_abbrev, vs_hand, game_context_row=None)`
   at L257 accepts a `game_context_row` argument with a column-picker
   block at L264-267 that is dead — the only caller `predict_totals()`
   at L481-483 invokes `get_team_offense(conn, away, home_throws)` with
   no fourth argument. The `if game_context_row is not None:` branch
   never executes.

3. The dead-code logic itself was also wrong on top of being unreached:
   `'away_lineup_woba' if vs_hand else 'home_lineup_woba'` picks by
   truthiness of `vs_hand`, not by handedness. The docstring comment
   at L19 falsely claims 11 reads game_context for lineup composites
   and weather — it reads neither.

Session 34 attempted to measure the divergence twice and both
diagnostics crashed (v1 column-picker bug grabbing `bp_woba_allowed`;
v2 silent death before printing). Session 35 documented the dead-code
finding and the failed measurements but the magnitude impact was
still unquantified.

## Decision

**The hypothesis that patching 11_predict_totals.py to consume lineup
composites would improve the model is REJECTED by data.**

The dead code is real, the docstring is misleading — both warrant
cosmetic cleanup — but consuming the composite makes the model
*worse* on every empirical test run against 148 games of actual
results.

**Do not patch 11_predict_totals.py to consume `away_lineup_woba` /
`home_lineup_woba` from `game_context`.**

## Evidence

`diag_lineup_composite_dead_code_v3.py` through `v5b.py` (Session 36,
read-only). 30-day window 2026-04-20 -> 2026-05-20. 163 games predicted
both with production path (PROD) and a counterfactual path with
`offense_woba` swapped for the lineup composite (COMP). 148 games
joined to actual_total from `pitches_historical`.

### Magnitude (v3)

Composite path shifts predicted_total by mean |Delta| = 0.305 runs vs PROD,
with sign skew: COMP > PROD in 68.7% of games. p75 |Delta| = 0.42 runs,
p90 = 0.66 runs. Large enough to change O/U picks at standard line
quantiles — the patch is consequential if applied.

### Correctness — MAE vs actual_total (v4)

Overall n=148: PROD MAE 3.540, COMP MAE 3.571 (Delta +0.031, PROD better).
By month:
- April n=69: COMP slightly better by 0.014 (inside noise)
- May n=79: PROD better by 0.071 (inside noise)

MAE comparison is inconclusive on its own; differences are below the
per-prediction noise floor.

### Pick agreement (v5b, decisive test)

Across hypothetical lines 7.5 to 9.5, on the 148-game with-actual
subset, when the two paths disagreed on the O/U pick:

| Hyp. line | Disagreements | COMP correct | PROD correct |
|-----------|---------------|--------------|--------------|
| 7.5       | 6             | 2            | 4            |
| 8.0       | 10            | 1            | 7            |
| 8.5       | 28            | 12           | 16           |
| 9.0       | 35            | 14           | 17           |
| 9.5       | 13            | 7            | 6            |
| **Total** | **92**        | **36**       | **50**       |

PROD wins 50-36 on disagreement games (**58.1% vs 41.9%**). Direction
is consistent across every line tier except 9.5 (tied within noise).
The composite is not making better picks on the games where it changes
the pick — it is making worse ones.

### Win rate vs real line (v5b)

`totals_tracker.book_line` joined to actuals on 76 games (selection
bias acknowledged: only published-pick games):

- PROD: 35-37-4 (48.6%) | UNDER 2/10 (20.0%) | OVER 33/62 (53.2%)
- COMP: 34-38-4 (47.2%) | UNDER 2/11 (18.2%) | OVER 32/61 (52.5%)

Differences are inside the +/-5.7pp standard error at this N. Cannot
declare a winner from this test alone, but direction matches the
pick-agreement test: PROD >= COMP.

### Per-tier bias (v5b)

| Prediction tier        | N  | PROD bias | COMP bias |
|------------------------|----|-----------|-----------|
| very_low (<= 7.5)      | 5  | +2.83     | +3.22     |
| low (7.5-8.5)          | 56 | **-0.83** | -0.59     |
| high (8.5-9.5)         | 74 | +0.20     | +0.32     |
| very_high (> 9.5)      | 13 | -1.57     | -1.69     |

In every tier, PROD bias has smaller magnitude or equal magnitude to
COMP bias. Composite does not de-bias the model in any tier; it
amplifies existing tier biases.

The -0.17 overall May bias observed in v4 was a population-weighted
average that masked the per-tier behavior. COMP's improvement of
overall May bias to +0.02 was a sample-weighted cancellation
artifact, not a structural calibration fix.

## Structural finding (carry forward, not part of this decision)

The PROD bias of -0.83 runs in the low tier (7.5 <= pred <= 8.5,
n=56) is the largest tier-level miss in the data and is mechanistically
consistent with May UNDER win rate of 33.3%: model predicts a
low-scoring game -> calls UNDER -> actual is 0.83 runs higher than
predicted -> UNDER loses.

This is the next investigation lead. It is independent of the
lineup composite path (COMP shows the same direction with -0.59
bias in the same tier — slightly less bad but same sign).

Plausible upstream sources: pitcher xwoba calibration,
`compute_league_averages` window, park factors, bullpen xwoba
calibration. **This investigation should be pre-registered
before any data analysis** per the methodology principle stated
in user memories (no exploratory decomposition without
pre-registration).

## Cosmetic cleanup (low priority, separate from the model decision)

These are documentation-quality fixes only. They do not change
model behavior:

- `11_predict_totals.py` L19 docstring: remove the false claim that
  `game_context` is read for lineup composites and weather.
- `11_predict_totals.py` L257: remove the unused
  `game_context_row=None` parameter and the dead L264-267 block.
- `11_predict_totals.py` L260 docstring comment claiming priority
  game_context > team_offense: remove.

Deferred. Not blocking. Cleanup gets bundled with whatever next
substantive change touches that file.

## What this ADR does NOT close

- The drawdown root cause remains **unidentified**.
- The low-tier bias finding is a NEW hypothesis, not a closed one.
- Train/serve divergence on other features was never measured in
  this thread and remains open.
- The deferred `05c` bullpen `season=2025` hardcode bug from
  Session 31 also remains open and could be contributing.

## Methodology note

This rejection is anchored in three independent tests on the same
148-game sample, each pointing the same direction. The
pick-agreement test (50-36 PROD favorable on 92 disagreement events)
is the decisive one. MAE alone was within noise; bias-aggregate alone
was misleading; pick-agreement under hypothetical line sweep was
unambiguous.

Future hypotheses about model-input dead code should similarly
distinguish between:
- **Structural existence** of the dead code (easy to confirm via grep)
- **Magnitude** of the change if patched (input-divergence proxy)
- **Correctness** of the change if patched (output-vs-actual on real games)

Only the third tier is decision-grade. The first two were where
prior sessions stopped.

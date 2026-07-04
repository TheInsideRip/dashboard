# ADR-059 (DRAFT / Proposed): ML/RL full-slate market capture & forward edge instrumentation

**Status:** DRAFT / Proposed — NOT accepted. **Authorizes nothing.**
**Date:** 2026-06-24
**Supersedes / superseded by:** none (draft)
**Relates to:** ADR-049 (selected `bet_tracker` forbidden for fitting — the ML/RL
analogue is the same trap), ADR-051 (totals leakage — point-in-time discipline),
ADR-052 (edge-test detection floor / breakeven-plus bar), ADR-055/056 (outcome-
column integrity; "clean" ≠ "correct"), ADR-058 (the K-prop instrumentation
pattern this ADR mirrors for ML/RL).

> **THIS DRAFT AUTHORIZES NOTHING.** No betting decision, no daily pick, no
> production wiring, no table creation, no serving/resolver/tagger/batch change,
> and no live deployment is authorized by this draft. It records an inventory
> finding and a *proposed* instrumentation design for later human review.

---

## Context

A read-only live-DB inventory (`tools/audit_mlrl_market_inventory_ro.py`,
`audits/mlrl_market_inventory_ro_YYYYMMDD.txt`) was run to determine whether a
clean ML/RL betting-edge study is possible today.

**Finding (pinned to live read-only audit, 2026-06-24).**
Audit report: `E:\\mlb_model\\audits\\mlrl_market_inventory_ro_20260624.txt`.
Live DB inventory: **108 total tables, 57 relevance-filter matches.**

- **No `mlrl_full_slate` table exists** — zero occurrences in the inventory.
- `mlrl_tracker`: **1,235 rows, 2026-03-31 → 2026-06-23**; market fields
  `spread_line`, `book`, `book_price`, `implied_prob` present — but it is a
  **selected +edge bet log, NOT a full opportunity universe** (the structural
  analogue of `bet_tracker`; forbidden as an edge basis per ADR-049).
- `mlrl_streak_picks`: **167 rows, 2026-04-07 → 2026-06-21** — a **derived pick
  log, NOT a full opportunity universe.**
- `game_odds_lookup`: **918 rows, 2026-04-08 → 2026-06-23**; holds raw ML odds
  (`away_ml_price`, `home_ml_price`) — but is **insufficient for edge validation**:
  no resolved result fields, no RL market rows, no model probability, no edge
  fields, no side-row universe, and no point-in-time / write-once guarantee.
  (It is a price cache, not an opportunity universe; usable only as evidence the
  odds fetch exists, not as a study basis.)
- Existing `full_slate` tables cover **other markets**, not ML/RL:
  `k_prop_full_slate` (**313 rows** at this run; ADR-058 snapshot was 234;
  SCHEMA.py snapshot was 57 — same table, three dated snapshots) is **market-blind**;
  `totals_full_slate` (**295 rows**) has **no market fields** and is on the
  **leaky serving path**; `totals_full_slate_lines` (**156 rows**) has lines but
  **no results**. None cover ML/RL.

This is the exact structural defect ADR-049 identified for K props in
`bet_tracker`, and the gap ADR-058 closed (forward) for K predictions via
`k_prop_full_slate` — but there is **no ML/RL equivalent**.

**Conclusion.** Live inventory confirms the ADR-059 premise: ML/RL has selected
market logs but no full-opportunity, point-in-time, side-separated market universe.
Therefore ML/RL remains **RESEARCH-ONLY**. The next valid step is a separately
approved full-slate ML/RL market-capture build, **not** historical edge validation
from selected logs.

**The blocker is INSTRUMENTATION, not a newly proven signal defect.** The pipeline
already fetches ML/RL odds (to populate the selected `mlrl_tracker`); it simply
does not persist the *full slate* of those odds before the edge gate.

## Position (binding, carried into this draft)

- **ML/RL has NO validated live edge today.** No leak-clean, side-separated,
  full-universe, vig-cleared ML/RL backtest exists in the ADR record. Selected
  `mlrl_tracker` unit results (e.g. early home-dog tallies) are **below the
  150-bet revisit bar, have no holdout, and no CLV** — a hypothesis, not an edge.
- **Selected tracker rows cannot prove edge.** Fitting, calibrating, or grading an
  edge claim on `mlrl_tracker` re-introduces selection bias (ADR-049 logic). The
  selected log may be USED only to characterize what was historically bet, never to
  validate a forward edge.
- **Prediction accuracy is not betting EV.** Model-vs-actual-winner accuracy, or
  model-vs-market agreement, is **not** edge evidence (ADR-058). Only EV after
  actual vig on the full universe counts.

## Purpose

Create a **full opportunity universe** for ML and RL so a future, separately-
approved study can test for a real, vig-cleared edge — side-separated, on
point-in-time data, with fragility and out-of-sample controls. This ADR designs
the capture; it does not run the study and does not authorize betting.

---

## Build spec (DESIGN ONLY — no implementation authorized)

### Table `mlrl_full_slate` (full universe; one row per game × market × side × book)

The table MUST store **every side of every game BEFORE any selection**:
- both ML sides (home, away) and both RL sides (-1.5 favorite, +1.5 dog),
- for every game on the slate,
- captured at decision time, not after the bet filter.

**Served / market-at-decision fields (WRITE-ONCE):**
- `game_pk`, `game_date`, `season`, `away_team`, `home_team`
- `market`  — 'ML' | 'RL'
- `side`    — 'home' | 'away'
- `spread_line`  — NULL for ML; +1.5 / -1.5 for RL
- `book_line` (where applicable), `book_price`, `book`
- `consensus_price`, `n_books`  (if available)
- `market_ts`  — timestamp of the captured market
- `model_prob`, `implied_prob` (no-vig), `edge_pct`
- `model_version`, `feature_version`
- `proj_starter_source`, `fallback_flag`
- `logged_at`

**Close-market fields** — companion table `mlrl_full_slate_close`
(`game_pk`, `market`, `side`, `close_price`, `close_book`, `close_ts`),
for CLV / open-to-close movement.

**Resolver-owned fields (IDEMPOTENT UPDATE ONLY):**
- `actual_winner`, `actual_margin`, `result_hit`
- `void_status`  — scratch / postponement / void
- `pnl`
- `resolved_at`

### Integrity requirements
- **Write-once** on served + market columns: first-write wins; reruns MUST NOT
  overwrite the original served prediction or market snapshot. Enforce via a
  `UNIQUE(game_pk, market, side, book)` key + `INSERT OR IGNORE` (NOT the
  ADR-058 UPSERT pattern, which is not write-once).
- **Resolver fields update idempotently**, only `WHERE resolved_at IS NULL`, and
  only through a dedicated resolver — never the serving writer.
- **Outcome verification:** resolved winner/margin MUST be reconciled against the
  official MLB Stats API (the ADR-055/056 lesson: an outcome column that nothing
  cross-checks can be silently wrong — "clean" ≠ "correct").
- **Point-in-time:** every served feature must be known before `market_ts`; no
  season-final or post-game input (ADR-051 discipline).

### Plumbing (design, not authorized)
- `08` persists the **full** ML/RL market slate it already fetches into
  `mlrl_full_slate` **before** the edge/selection step.
- A new `09g_mlrl_full_slate_resolve.py` (sibling of `09f`) resolves
  winner/margin/void/PnL idempotently from the API.
- An evening/next-morning close resolver populates `mlrl_full_slate_close`.

---

## Future testing plan (DESIGN ONLY — do not execute)

Runs only AFTER the build is approved, implemented, and enough clean forward data
has accumulated. Compare: (1) market-only baseline, (2) raw model, (3)
calibrated/shrunk model.

**Side-separated — tested independently, never pooled across opposite sides:**
- ML favorite
- ML dog
- RL -1.5 favorite
- RL +1.5 dog

For each side: edge-bucket gradient, n / WR / ROI / avg odds per bucket,
bootstrap CI, 2024 discovery → 2025 holdout → both 2025 halves → 2026 forward,
EV after **actual** vig, CLV where close data exists. Apply the ADR-052
breakeven-plus bar (ROI ≥ +1.5% at actual juice) with large-n pooling and a
multiple-comparisons funnel.

**Fragility rejection** (any one fails → REJECT): profit from one tiny bucket,
one team/park/book/month/price-range; result vanishes excluding outliers; depends
on stale/deprecated/leaky tables; depends on the selected log; negative EV after
actual juice; negative or unavailable CLV where required.

## Prohibitions (carried from ADR-049/051/055/056/058)
- No fitting, calibration, or grading on the selected `mlrl_tracker`.
- No selected-bet-only universe.
- No season-final / post-game / leaky inputs.
- No proxy inheriting another signal's ROI (ADR-057 discipline).
- MAE / accuracy parity is NOT edge evidence.

## Deployment gates (ALL required before any ML/RL reactivation)
- clean full-slate forward data only
- served predictions + input snapshot + market snapshot persisted point-in-time, write-once
- winner/margin reconciled to API; void/scratch/PPD resolved
- calibration monotonic across edge buckets, per side
- positive out-of-sample EV after vig, per side, with adequate n
- no fragile single-bucket concentration
- non-negative CLV where close data is part of the gate
- confidence/bootstrap intervals reported
- **explicit human approval before reactivation**

## Decision (DRAFT — proposed, not approved)
- ML/RL stays **RESEARCH-ONLY**; no live edge today.
- The next valid path is **full-slate market capture** (`mlrl_full_slate` +
  `mlrl_full_slate_close`), then later out-of-sample side-separated EV testing.
- Selected `mlrl_tracker` rows remain **forbidden** as an edge-proof basis.
- **No build, no wiring, no picks, no deployment authorized** until separately approved.

## Cross-references
- `tools/audit_mlrl_market_inventory_ro.py` — read-only inventory producing this finding.
- ADR-058 — the K-prop instrumentation pattern mirrored here (and its non-write-once UPSERT caveat, avoided here).
- ADR-049 — selected-subset fitting prohibition (the `bet_tracker` analogue of `mlrl_tracker`).
- ADR-055/056 — outcome-column integrity; reconcile resolved results to the API.
- DEPENDENCIES.py — `08` ML/RL odds fetch (currently persisted only to the selected `mlrl_tracker`).

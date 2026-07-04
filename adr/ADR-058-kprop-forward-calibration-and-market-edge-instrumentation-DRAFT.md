# ADR-058 (DRAFT / Proposed): K-prop forward calibration & market-edge instrumentation

**Status:** DRAFT / Proposed — NOT accepted. Authorizes nothing.
**Date:** 2026-06-21
**Supersedes / superseded by:** none (draft)
**Relates to:** ADR-048 (K H_NULL / tail overconfidence), ADR-049 (predictions not
persisted — full-slate gap), ADR-050 (lineup composite not point-in-time).

> **THIS DRAFT AUTHORIZES NOTHING.** K props remain DARK. No betting decision is
> authorized. No build is authorized. No calibration fit is authorized. No
> production code, table, config, batch file, tagger, resolver, serving script, or
> betting change is authorized by this ADR draft. It records an inventory finding
> and a *proposed* (not approved) instrumentation path for later human review.

---

## Context

A read-only forward-instrumentation audit was run against the live DB to determine
whether a clean K-prop edge study is possible today.

**Ghost P0 correction (recorded so it is not re-litigated):** A prior concern held
that the forward full-slate writer `k_prop_full_slate` "stopped writing after
2026-06-13." This was a **stale-`SCHEMA.py` artifact** — `SCHEMA.py` carried an old
57-row / 2-day (2026-06-12→06-13) snapshot captured around the table's debut. The
live DB **refutes** this:

- `k_prop_full_slate` = **234 rows**, `game_date` span **2026-06-12 → 2026-06-20**.
- `logged_at` current through **2026-06-20 12:08:39** (min `2026-06-13 12:22:04`).
- Rows present for **every slate day** 06-12 through 06-20 (counts 17–30/day, tracking
  real slate size).
- Independent corroboration: `totals_full_slate` spans to 2026-06-20; `pull_log`
  shows the daily chain running through 2026-06-21.

**The forward full-slate writer is HEALTHY and writing daily.** There is no
write-path failure. The `SCHEMA.py` snapshot line is simply out of date.

**The current blocker is INSTRUMENTATION, not a newly proven substrate defect.**
The forward writer captures clean predictions, inputs, and resolved actuals, but it
does not capture the market and validity data needed to evaluate betting edge.

**Prior-gap status (going forward):**
- ADR-049's full-slate prediction-persistence gap **appears CLOSED GOING FORWARD**:
  `k_prop_full_slate` now writes the **full** starter slate (bet and non-bet), not
  just the selected subset.
- ADR-050's lineup-mutation gap **appears CLOSED GOING FORWARD**: the lineup
  composite (`lineup_k_pct`, `has_lineup`) is now **frozen at serve time** into
  `k_prop_full_slate` from the `predict_pitcher` return dict, rather than re-read
  from a mutated `game_context`.

**Caveats on those closures (still open):**
1. **Not fully write-once.** `save_full_slate_k` uses an UPSERT that can **refresh
   the prediction/input fields on rerun** (`predicted_k`, `lineup_k_pct`, etc. via
   `ON CONFLICT … DO UPDATE`). Resolver-owned columns (`actual_k`, `tbf`, `was_bet`,
   `resolved_at`) are correctly left untouched, but the served prediction/input
   snapshot is **not write-once protected**. Write-once or first-write guarding is
   still required before the table can be treated as fully point-in-time safe.
2. **Composite-only lineup snapshot.** The frozen lineup snapshot stores the
   **scalar composite** (`lineup_k_pct`) but **not the exact lineup IDs** used. This
   limits auditability and reproducibility of the as-of lineup.

**Required prior-ADR references (carried forward, not re-opened):**
- **ADR-048:** the K-prop drawdown was **real** — not mainly a tracker artifact and
  not mainly the already-fixed v2 frozen-window defect. Clean-substrate losses
  persisted; the dominant signature was **tail overconfidence**.
- **ADR-049:** fitting calibration on `bet_tracker` is **forbidden** — `bet_tracker`
  is the **selected +3%-edge betting subset** (verified live: `edge_pct` floor
  ≈ 3.23%), not the full prediction universe; fitting on it re-introduces the exact
  selection bias under study.
- **ADR-050:** historical R3 confirmed-lineup reconstruction remains **invalid** —
  mutable `game_context` lineup composites cannot reproduce the served predictions
  (43/45 mismatches were on `lineups_confirmed=1` games).

---

## Current state (verified, read-only)

- `k_prop_full_slate` is writing **forward full-slate rows daily** (234 rows,
  through 2026-06-20).
- It currently stores **predictions and some inputs** (`predicted_k`, `raw_k_pct`,
  `tto_k_pct`, `has_tto`, `regressed_k`, `whiff_rate`, `blended_k`, `adj_k_rate`,
  `est_bf`, `cum_bf`, `cum_games`, `confidence`, `conf_label`, `source`).
- It **resolves actual K and TBF at a high rate** (`actual_k` non-null 226/234 ≈
  96.6%; `tbf` non-null 226/234; `resolved_at` set on resolved rows).
- It stores **`was_bet`** (138 of 234 flagged).
- It stores **`lineup_k_pct`** and **`has_lineup`** (105 rows populated).
- It does **not** currently store sufficient **market data** for betting-edge
  research.
- It does **not** currently store sufficient **close-line data** for CLV research.
- It does **not** currently store sufficient **opportunity/validity flags** for
  short-outing, opener, scratch, postponement, or void controls (only `tbf`; no IP,
  no started/opener/void flags).

---

## Gap analysis

Current `k_prop_full_slate` can support **limited prediction-accuracy and
calibration review** (predicted_k vs actual_k), but **cannot yet support a real
betting-edge study**, because it lacks:

- market line
- over odds
- under odds
- book
- market timestamp
- close line
- close over odds
- close under odds
- close timestamp
- exact lineup IDs used
- lineup confirmed flag
- model version / hash
- feature version / hash
- projected starter source
- fallback flags
- estimated IP / leash
- actual IP
- pitcher-started flag
- opener / bulk flag
- scratch / postponement / void status
- bet result fields tied to the stored line/odds
- EV-at-decision fields (only if later authorized)

Historical fallbacks remain unavailable: the selected `bet_tracker` subset (ADR-049)
and the R3 confirmed-lineup reconstruction (ADR-050) are both forbidden for fitting.
Thus a clean edge study depends on **forward** instrumented data that does not yet
exist.

---

## Decision (DRAFT — proposed, not approved)

- **K props remain DARK.**
- The next valid path is **forward full-slate instrumentation** plus **later
  out-of-sample calibration/EV testing**.
- Historical selected `bet_tracker` rows remain **forbidden** for calibration
  fitting.
- Historical R3 confirmed-lineup reconstruction remains **forbidden** for fitting.
- **No reactivation is authorized.**
- **No build is authorized** until separately approved.

---

## Build spec (DESIGN ONLY — no implementation authorized)

A later **approved** build should add to, or companion-store alongside,
`k_prop_full_slate`:

**Market-at-decision fields** (capturable from data `08` already fetches via
`parse_k_props`, before the +3% selection):
- `book_line`
- `over_price`
- `under_price`
- `book`
- `market_ts`
- `consensus_line` (if available)
- `n_books` (if available)

**Close-market fields:**
- `close_line`
- `close_over_price`
- `close_under_price`
- `close_ts`
- close source / book (if available)

**Point-in-time identity / version fields:**
- `model_version` or model hash
- `feature_version` or feature hash
- `projected_starter_source`
- `pitcher_throws`
- `fallback_flag`
- `source` / provenance hardening

**Lineup audit fields:**
- `lineup_confirmed`
- exact `lineup_ids` used (preferably JSON)
- preserve existing `lineup_k_pct`
- preserve existing `has_lineup`

**Opportunity / validity fields:**
- `est_ip` or leash estimate
- `actual_ip`
- `pitcher_started`
- `opener_bulk_flag`
- `scratch_void_status`
- postponement / void flag
- resolver timestamp for these fields

**Decision / result fields (only if later authorized):**
- `side_selected`
- `ev_at_decision`
- `bet_result`

**Write-once requirement:** Served prediction / input / market fields must be
**write-once or protected by a first-write guard**. Resolver-owned fields may update
later, but only through **idempotent** resolver logic. Historical reruns must **never
overwrite** the original served prediction, the original input snapshot, or the
original market snapshot. (This closes Caveat #1 above; today `save_full_slate_k`
does not enforce it.)

**Workflow requirement:** A later approved build should:
- make `08` persist the **K market data it already fetches** into the full-slate
  table **before** the +3% selection step;
- add **close-line / close-odds capture** via an evening or next-morning close
  resolver;
- extend `09e` (or a companion resolver) to resolve **actual IP, pitcher-started
  flag, opener/bulk, scratch/postponement/void status, and bet result**;
- keep **served columns and resolver-owned columns clearly separated**.

---

## Future research plan (DESIGN ONLY — do not execute)

Research **must not run** until enough clean forward data exists **after** the
instrumentation build.

The future study should compare:
1. market-only baseline
2. raw model
3. calibrated / shrunk model

It should evaluate:
- raw `predicted_k` vs actual K
- market line vs actual K
- model edge buckets: `predicted_k − book_line`
- OVER and UNDER separately
- line buckets: 3.5, 4.5, 5.5, 6.5, 7.5+
- pitcher K-rate tiers
- opponent K-rate tiers
- lineup confirmed vs not confirmed
- expected TBF/IP buckets
- actual TBF/IP miss buckets
- short-outing failures
- book / price buckets
- CLV / open-to-close movement
- EV after vig using actually available odds
- sensitivity excluding fallback rows
- sensitivity excluding opener / scratch / void cases
- uncertainty / confidence intervals

Prohibitions (carried from ADR-049/050): no fitting on `bet_tracker`, no
selected-bet-only universe, no R3 reconstruction from mutable `game_context`. MAE
parity is **not** edge evidence; prediction accuracy is **not** betting EV.

---

## Deployment gates

K props **cannot** go live unless **all** of the following are true:
- clean full-slate forward data only
- exact served predictions persisted point-in-time
- exact input snapshots persisted point-in-time
- market line / odds / book / timestamp persisted
- close line / close odds persisted (if CLV is part of the gate)
- actuals and opportunity metrics resolved
- calibration monotonicity across edge buckets
- positive out-of-sample EV after vig
- no profit concentrated in one fragile bucket
- no materially negative CLV (if CLV is available)
- adequate sample size by side and bucket
- uncertainty / confidence intervals reported
- no selected-bet-only fitting
- no mutable historical lineup reconstruction
- **explicit human approval before reactivation**

---

## Cross-references
- `08_odds_and_edges.py::save_full_slate_k` — forward full-slate writer (UPSERT;
  not write-once).
- `08_odds_and_edges.py::parse_k_props` — already fetches K line + over/under
  prices + book (currently only persisted to `bet_tracker`).
- `09e_k_full_slate_resolve.py` — resolver (idempotent; fills `actual_k`/`tbf`,
  flags `was_bet`); wired in `resolve_morning.bat` step [1/8].
- ADR-048 / ADR-049 / ADR-050 — see Context.
- `audit_live_arsenal_substrate.py` / ADR-057 — unrelated (Filter E); cited only to
  confirm the 057 number is taken, making 058 the next free ADR.

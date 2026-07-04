# ADR-059 — ML/RL Full-Slate Capture: SOURCE AUDIT (FILLED)

**Status:** DRAFT / Proposed companion to ADR-059. **Authorizes nothing.**
**Date:** 2026-06-24
**Scope:** documentation only — no table creation, no production-code change, no DB write, no edge test, no picks.
**Authority:** This FILLED audit is the **authoritative build-prerequisite list** for the
ML/RL full-slate capture. Where it differs from the earlier implementation-plan DRAFT, **this
file supersedes** that plan's reuse assumptions (the plan assumed more mirroring than the live
source supports). ADR-059 itself remains DRAFT and is not modified by this file.

Source read by CC on E:\mlb_model: `08_odds_and_edges.py` (1,878 lines),
`09c_mlrl_results.py` (494 lines). All reads were read-only (grep/sed/read); nothing modified.

---

## Headline findings (load-bearing)

1. **No pre-gate full universe exists today.** The edge gate `if edge >= MIN_MLRL_EDGE` is
   applied inline, inside the append (08:1586, :1607, :1652). `all_edges` only ever holds the
   model-favored side, >=+3% edge, per book. **No variable holds every side x book x market
   before the filter.**

2. **Therefore `save_full_slate_mlrl` is NOT a one-line writer insertion.** Unlike
   `save_full_slate_totals` (which had a full-slate object to persist), the ML/RL path never
   builds the universe. The build must **construct** it: append all sides x books x markets
   **unconditionally** inside the `for book -> for market` loops (08:1570-1665), with the edge
   `if` removed, before the dedup at :1672. This is a code addition, not a bolt-on. (Corrects
   the earlier plan's "fires before the gate, mirrors totals" framing.)

3. **`game_pk` and the fallback signal are available pre-gate but currently dropped.** `pred`
   carries `game_pk` (08:1319) and four source fields `away_p_source / home_p_source /
   away_off_source / home_off_source` (08:1329-1332). The edge dict (08:1587-1599) copies
   neither. They are capturable at the match point (`pred = p`, 08:1563) — not missing, just
   discarded. `fallback_flag` is **derivable**: true if any of the 4 source fields is in
   {league_average, league_avg, default}.

4. **Price = best-book-of-the-model's-pick (edge-maximized) — CONFIRMED DEFECT.** Dedup
   (08:1672-1684) keeps `PRIORITY_BOOKS` first, else breaks ties on
   `e['edge_pct'] > existing['edge_pct']` — the highest price **for the side the model already
   chose**. This is the price-after-edge leak (the ML/RL analogue of ADR-049 bet selection,
   moved to price selection). A `price_source_policy` frozen **before** edge computation is
   **mandatory**; the current behaviour is **forbidden** as the tested price.

5. **`game_odds_lookup` is not a valid opportunity universe.** It holds ML prices only
   (away_ml_price/home_ml_price), no RL, no side rows, no model_prob/edge, no market_ts, no
   write-once guarantee. Reference only; capture must be independent.

6. **`09c_mlrl_results.py` provides winner/margin/RL/PnL logic to reuse — but `09g` must add
   what `09c` lacks.** See the resolver table below. Two integrity items are **written fresh,
   explicitly NOT mirrored**: (a) void/PPD resolution (09c has none — `'void'` appears only as a
   WHERE exclusion, set externally, never written); (b) idempotency key (09c uses
   `result_hit IS NULL`; `09g` must use `resolved_at IS NULL` per spec). Copying `09c` wholesale
   would inherit a resolver that silently never resolves voids — the ADR-055/056 failure mode.

7. **Write-once template = `save_full_slate_totals` (08:707)** — append-only, check-then-INSERT
   per (game_date, game_pk) (08:758-777). **Do NOT** mirror `save_full_slate_k` (08:574, UPSERT/
   last-write-wins) or `save_full_slate_lines` (08:790, UPSERT). (Totals uses check-then-insert
   rather than `INSERT OR IGNORE`; same write-once semantics, either mechanism satisfies the ADR.)

8. **ADR-059 remains DRAFT / Proposed and authorizes nothing.**

---

## Section 4a — exact identifiers in the ML/RL block

| Plan field | Exact var in source | Note |
|---|---|---|
| game_pk | `pred['game_pk']` (08:1319) | in pred, **dropped** from edge dict |
| game_date | `game_date` (func arg) | ok |
| away_team | `away_abbrev` (full `api_away`) | edge `'away'` |
| home_team | `home_abbrev` (full `api_home`) | edge `'home'` |
| market | `market_key` in {'h2h','spreads'} | edge `'market'` |
| side | `pick` = `team_abbrev` | **team abbrev, not home/away** — KEY-CRITICAL derivation, see below |
| spread_line | `point` | None for h2h |
| book_price | `away_price`/`home_price`/`price` | edge `'book_price'` |
| book | `book_title` (+ `book_key`) | edge `'book'` |
| model_prob | `model_prob` (<- `pred['away_wp']`/`home_wp`/`*_rl_prob`) | ok |
| implied_prob | `implied` (`american_to_implied_prob`) | per-side, NOT pair-devigged — note for any no-vig test |
| edge_pct | `edge` = `(model_prob - implied)*100` | ok |
| fallback/source | `pred['{away,home}_p_source']`, `pred['{away,home}_off_source']` (08:1329-1332) | values include league_average/league_avg/default -> derive `fallback_flag` |

**`side` is key-critical, not cosmetic.** The proposed `UNIQUE(game_pk, market, side)` assumes
`side in {home,away}`. Source carries `pick` as a team abbreviation. The derivation
`side = 'home' if pick == home_abbrev else 'away'` is part of the uniqueness key — if it is
wrong, the key collapses the wrong rows. Treat as load-bearing.

---

## Sections 5-6 — `09c_mlrl_results.py` resolver to (partly) mirror

| Item | Exact rule in 09c | 09g action |
|---|---|---|
| Winner | `margin = home_runs - away_runs`; >0 home, <0 away, ==0 'TIE' (251-257) | mirror |
| Margin stored | `abs(margin)` (315) | mirror |
| ML hit | `pick == winner`; TIE -> hit=None (push) (262-267) | mirror |
| RL cover (differs from ML) | spread-aware (269-293): fav (spread<0) hits if margin > abs(spread); dog (spread>0) hits if margin > -spread; away uses -margin; default spread -1.5 if NULL | reuse as-is (spread IS applied) |
| PnL (american->units) | `calc_pnl` (84-93): hit & odds>0 -> odds/100; hit & odds<0 -> 100/abs(odds); push -> 0.0; miss -> -1.0 (1-unit, 3dp) | mirror |
| Void/PPD | **None.** Non-final stamps game_status, leaves result_hit NULL for retry (233-246, gate 146). 'void' only a WHERE exclusion (192), set externally | **WRITE FRESH** — 09g sets `void_status` explicitly, leaves pnl NULL |
| Idempotency | `WHERE result_hit IS NULL AND game_status != 'void'` (192) | **CHANGE** — 09g uses `WHERE resolved_at IS NULL` per spec |

Outcome source: `get_game_score` (134) pulls MLB Stats API; final gate
`status in ('Final','Game Over','Completed Early')` (146) — satisfies ADR-055/056 reconcile-to-API.

---

## Section 7 — ML and RL both pre-gate? CONFIRMED YES
`get_mlrl_odds` issues one bulk call `markets=f"{ML_MARKET},{RL_MARKET}"` (08:220); both h2h and
spreads parsed from the same in-memory object (08:1577, :1622) before any gate. Not separate fetches.

## Section 8 — price representation: best-book-of-pick (priority-preferred)
Proof: dedup 08:1672-1684 + `PRIORITY_BOOKS = ['fanduel','draftkings','betmgm','caesars',
'pointsbetus','betonlineag','bovada', ...]` (08:101). Priority book first, else max edge_pct =
best price for the chosen side. Price-after-edge confirmed.

---

## Build-prerequisite list (authoritative)

1. **Construct a genuine pre-gate universe** — append all sides x books x markets with the edge
   `if` removed (finding 1/2). Without this, "full slate" is still selected.
2. **`side` derivation** — `pick == home_abbrev -> 'home'`; KEY-CRITICAL for uniqueness.
3. **`fallback_flag`** from the 4 `*_source` fields (finding 3) — carry + threshold.
4. **`price_source_policy`** (finding 4) — frozen before edge; best-book-of-pick forbidden.
   Store as a NOT NULL column on every row, identical regardless of model-favored side.
5. **Void resolution in `09g`** — write fresh; 09c has none.
6. **Idempotency on `resolved_at IS NULL`** in `09g` — differs from 09c.
7. **Write-once** — mirror `save_full_slate_totals`, not K's UPSERT.

---

## What this file does NOT do
No table created. No production code modified. No DB write. No edge test. No pick. ADR-059
itself unchanged and still DRAFT / Proposed.

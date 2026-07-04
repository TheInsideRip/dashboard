# ADR-057 — Filter E live parent-exact rebuild is blocked; confirmed-lineup rebuild is proxy-only

**Status:** Accepted
**Date:** 2026-06-20
**Context:** First live `--detect` drill for the Filter E forward-test harness
exposed a substrate gap (not a signal result): `away_arsenal_bad` has no live
2026 source. A read-only substrate reconstruction audit
(`audit_live_arsenal_substrate.py`) was run to determine whether the exact
parent construction can be rebuilt live for 2026. This ADR records the verdict
so it is not re-litigated.

---

## 1. Parent signal (what Filter E actually is)

- Filter E = **away arsenal mismatch + BP P80 → OVER**.
- `away_arsenal_bad = -away_lineup_wv`.
- `away` means **home lineup vs away SP** (the away starting pitcher facing the
  home team's batters).
- Parent lineup source = the **actual played lineup**, derived from the game's
  own pitch rows: `pitches.groupby([game_pk, batting_team, batter]).size()`,
  top-9 batters by pitch count.
- Therefore the parent is a **post-game, actual-lineup mode** signal — NOT a
  live pre-game confirmed-lineup mode. The lineup it depends on is only fully
  known after the game has been played.
- Non-lineup windows (arsenal usage 60d, batter whiff-by-family 60d, team wOBA
  30d) end at `month_start` (strictly prior / as-of clean).

## 2. Live feasibility finding (2026)

- The deprecated `whiff_vuln_pit` table (the original `away_arsenal_bad` source)
  ends **2025-09-28**. There is **no live 2026 parent-exact `away_arsenal_bad`
  source**.
- `bp_prior_3d` (the other half of Filter E) **does** exist live
  (`bullpen_workload`, `game_context`), 2026 current.
- `game_context` provides 2026 **confirmed lineup IDs** (`away_lineup_ids`,
  `home_lineup_ids`, `lineups_confirmed`) — a pre-game (mode ii) lineup source.
  This is **not the same lineup mode** as the parent's post-game actual lineup.
- `game_context` has **0 rows for 2023-2025** (1,069 for 2026). Consequently the
  confirmed-lineup method **cannot be value-level proven against the parent on
  the historical backtest window (2023-2025) at all** — the only pre-game lineup
  data that exists, exists only in 2026.

## 3. Fidelity test (measured on 2026, the only year both lineup modes exist)

Holding all non-lineup inputs identical, comparing **confirmed pre-game lineup
(mode ii)** vs **actual played lineup (mode iii)** on 302 paired 2026 games:

| metric | value | parent-exact gate | result |
|---|---|---|---|
| correlation | 0.9784 | ~1.0 | FAIL |
| max absolute difference | 0.0333 | ~0 | FAIL |
| lineup Jaccard | 0.930 | — | — |
| Q75-side agreement | 0.983 | — | — |
| threshold-side flips | 5 / 302 | — | — |

Close, but **fails parent-exact value-level identity.** A confirmed lineup is a
different batter set than top-9-by-pitch-count actually faced (pinch hitters,
early exits, lineup-order vs PA-faced ranking), so the computed
`away_arsenal_bad` value diverges.

## 4. Decision

- **Label = `ONLY PROXY POSSIBLE`.**
- **Live parent-exact Filter E is BLOCKED.** It cannot be rebuilt for live
  pre-game detection because the parent depends on the actual played lineup,
  which is post-game information.
- A confirmed-lineup version is a **new proxy signal, not the parent signal.**
- The proxy **does NOT inherit** the parent's documented historical ROI
  (2024 +22% / 2025 −2%), its 3-year characterization, or its forensic-audit
  status (structurally-real / thin / tail-concentrated / breakeven-2025).
- **Do NOT run `--detect` for parent Filter E** until a parent-exact live
  substrate exists — which appears **impossible pre-game**, because the actual
  lineup is post-game information by definition.

## 5. Allowed future path

- If desired, open a SEPARATE research track:
  **"Filter E proxy — confirmed-lineup arsenal mismatch + BP P80."**
- That proxy must be backtested and/or forward-tested under its **own label**,
  with its **own thresholds**, its **own validation**, and **no inherited claims**
  from parent Filter E. The frozen parent thresholds (arsenal Q75 = −0.203736,
  BP P80 = 228) are NOT valid for the proxy without re-derivation.
- The forward harness (`forward_track_filter_e.py`) and odds adapter
  (`odds_adapter_filter_e.py`) remain built, pre-flight clean, and **not
  enabled**. They are not wired to any live signal and write nothing until a
  validated live signal exists.

---

## Cross-references
- `odds_adapter_filter_e.py:70` — `away_arsenal_bad = NO LIVE SOURCE`
  (this ADR explains *why* a live rebuild cannot recover parity, not just that
  the old table is gone).
- `audit_live_arsenal_substrate.py` — read-only audit producing this verdict.
- `rebuild_parent_arsenal_signal.py` / `parent_arsenal_3yr.py` — parent
  reconstruction and 3-year characterization (parent is structurally real but
  thin, tail-concentrated, breakeven 2025).
- `diag_bp_matchup_total.py:200-423` — original parent construction
  (actual-lineup, top-9 by pitch count).

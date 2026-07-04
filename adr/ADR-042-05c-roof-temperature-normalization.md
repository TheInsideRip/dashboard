# ADR-042: 05c closed-roof temperature normalization — outdoor temp poisoned dome totals

Status: Accepted
Date: 2026-06-05
Session: 43

## Context

`05c_pregame_context.py` writes the per-game `game_context` table that
downstream taggers and the totals model read at tag time. Among its
fields, `pull_weather(home_team, game_time_str)` populated
`weather_temperature_f` for each game from the Open-Meteo outdoor
forecast at the home ballpark's coordinates.

For closed-roof parks this is the wrong temperature. Open-Meteo returns
the **outdoor** air temperature, but a game played under a closed roof
happens in a climate-controlled ~72-74F environment regardless of the
weather outside. Chase Field (AZ) is the worst case: on a summer
afternoon Open-Meteo reads ~104F outside while the real in-stadium
temperature with the roof closed is ~74F — a 30-degree error fed
directly into the totals model as if it were the playing condition.

Temperature is a run-scoring input (hot air → ball carries → higher
totals). A spuriously hot dome game inflates the predicted total and
biases the model toward OVER.

### Observed impact

- Chase Field / AZ games carried `weather_temperature_f ≈ 104` in
  `game_context` when the real closed-roof temperature was ~74F.
- This fed inflated totals predictions. The 2026-06-04 LAD@AZ game
  published an OVER that lost: predicted 10.9 runs, actual 5. The
  inflated dome temperature is consistent with that over-prediction.
- WSH@AZ (and other Chase/dome games) were exposed to the same defect.

### Root cause

`05c_pregame_context.py` already carried a `DOMED_STADIUMS` dict
(TB = `dome`, seven others = `retractable`). `pull_weather` stored this
classification into the `dome_status` field — **but never applied it to
`temperature_f`**. The roof state was recorded for display and never
used to correct the temperature. The outdoor forecast flowed through to
`game_context.weather_temperature_f` unmodified for every park, closed
roof or not.

A second, separate defect lived in the same function: on a `requests`
exception `pull_weather` executed `return None`. The single caller does
`for k, v in weather.items()`, so a `None` return raised
`AttributeError` and crashed the whole pregame pipeline. This is the
2026-06-02 crash.

## Decision

Patch `pull_weather` in `05c_pregame_context.py` to normalize the
temperature for closed roofs using the **live MLB-posted roof state**,
not the static `DOMED_STADIUMS` capability flag. Three coupled changes,
all landed Session 43 (2026-06-05):

### Fix A — MLB condition-driven closed-roof normalization

`pull_weather` now takes a third argument `game_pk` (the single caller
at the weather step passes it; `game_pk` is already in scope there).
After the Open-Meteo pull, if `game_pk` is supplied, it reads
`gameData.weather.condition` from `statsapi.get('game', {'gamePk':
game_pk})`. **Only** when the condition string explicitly contains
`'Roof Closed'`, `'Dome'`, or `'Closed'` does it:

- replace `temperature_f` with `gameData.weather.temp` (the real
  in-stadium MLB temperature, float-parsed),
- set `wind_speed_mph = 0` (no wind under a closed roof),
- set `dome_status = 'closed'`.

On any **other, blank, missing, or ambiguous** condition — or any MLB
API failure, or an unparseable MLB temp — the Open-Meteo path is left
**unchanged** and the function logs a warning. The normalization is
never inferred from `DOMED_STADIUMS` (see Alternatives, option c).

(Verified on completed game_pk 825076: condition `'Roof Closed'`,
temp `'74'`, wind `'0 mph, None'` — the fix reads exactly these.)

### Fix B — audit column `weather_temperature_f_outdoor`

A new dict key `temperature_f_outdoor` always preserves the raw
pre-normalization Open-Meteo outdoor temperature; the closed-roof branch
never overwrites it. Via the caller's `weather_<key>` prefixing this
becomes `game_context.weather_temperature_f_outdoor` (REAL). The table
went from 65 to 66 columns. Because the write path is
`df.to_sql('game_context', conn, if_exists='append')` — which does NOT
add columns to an existing table — the column is created with an
**idempotent `ALTER TABLE game_context ADD COLUMN
weather_temperature_f_outdoor REAL`** guarded by `try/except
sqlite3.OperationalError`, run immediately before the `to_sql` append
(first-run path: the ALTER raises, and `to_sql` then creates the table
with the column from the DataFrame).

This gives a permanent audit trail: for any game one can compare the
applied `weather_temperature_f` against the outdoor `weather_temperature_f_outdoor`
and see whether (and by how much) roof normalization fired.

### Fix C — `pull_weather` never returns None

The `return None` on a `requests` exception is replaced: an API failure
(weather or MLB roof check) logs a warning, falls back to the Open-Meteo
path, and the function returns its result dict on **every** code path.
This removes the 2026-06-02 pipeline-crash failure mode at the caller's
`for k, v in weather.items()` loop.

## Alternatives considered and rejected

**(a) Constant normalization for domed parks.**
Whenever the home park is in `DOMED_STADIUMS`, overwrite `temperature_f`
with a fixed indoor constant (e.g. 72F). Rejected. It fabricates a
number rather than reading the real in-stadium temp the MLB API already
publishes, discards genuine variation, and — critically — is wrong for
retractable roofs that are **open** (a fixed constant would erase the
real outdoor conditions of an open-roof game at AZ/HOU/TEX/etc.).

**(b) Infer closed from `DOMED_STADIUMS`.**
Treat any park in `DOMED_STADIUMS` as closed and apply MLB/indoor temp.
Rejected. `DOMED_STADIUMS` is a **capability** flag (the park *can*
close), not a **live state**. Seven of the eight entries are retractable
roofs that are frequently open in fair weather; inferring "closed" from
the flag would wrongly normalize open-roof games and reintroduce the
inverse error (treating a genuinely 104F open-roof game as a 74F dome
game). Roof state must come from the live game feed, not a static map.

**(c) MLB condition-driven, normalize only when explicitly posted
closed — CHOSEN.**
Read `gameData.weather.condition` per game and normalize only when it
explicitly says closed; otherwise keep Open-Meteo untouched. This is the
narrowest correct rule: it fires exactly when the roof is known-closed,
never guesses, and degrades gracefully (open/blank/missing/error → no
change). The known cost is the pregame-timing limitation below.

## Consequences

### Positive

- Closed-roof games carry the real in-stadium temperature, removing the
  ~30F dome over-temperature that biased totals toward OVER.
- `weather_temperature_f_outdoor` gives a permanent, per-game audit of
  whether normalization fired and the outdoor value it replaced.
- The pipeline no longer crashes when a weather/MLB API call fails;
  `pull_weather` is now total (always returns a dict).
- The rule is robust to retractable roofs being open — those games stay
  on the correct outdoor forecast.

### Known limitation — unposted roof state at early pregame runs

The MLB `weather.condition` field is often **blank pregame** and is not
populated until closer to first pitch. Under option (c)'s "only
normalize when explicitly posted closed" rule, a Chase/dome game whose
roof state is not yet posted (`condition == ''`) **stays on the outdoor
temperature** until 05c is re-run closer to game time. So at a noon
pregame run a dome game can still read the outdoor temp. This is a
correct (conservative) outcome of the chosen rule, not a regression: the
fix never guesses closed. Mitigation: re-run 05c closer to first pitch,
when conditions are posted, to capture the normalized temperature.

### Forward note

The Mar-May 2026 totals drawdown window (ADR-035, Sessions 41-42) is not
re-graded by this fix. This corrects the input going forward; it does
not reconstruct historical `game_context` rows (a reconstruction would
leak current-state inputs — same no-backfill stance as ADR-031/ADR-032).

## Verification

All checks passed before declaring the fix done (Session 43):

- **Structural:** file backed up; `python -m py_compile
  05c_pregame_context.py` clean after the edit.
- **Function test — closed game (game_pk 825076):** `pull_weather('AZ',
  '', 825076)` returned `temperature_f = 74.0` (MLB in-stadium),
  `temperature_f_outdoor = 106.3` (Open-Meteo, preserved), `wind_speed_mph
  = 0`, `dome_status = 'closed'`.
- **Behavior test — full 05c re-run, 2026-06-05 slate:** 15 game contexts
  stored, no errors, no crash. Each game's stored row was cross-checked
  against its **live** `gameData.weather.condition`: every game fired the
  correct branch. No game tonight had an explicitly-closed condition
  posted (all `condition` blank or open), so all 15 correctly stayed on
  the Open-Meteo path. **WSH@AZ** specifically stayed on Open-Meteo at
  104.2F with `dome_status = 'retractable'` because its roof state was
  unposted (`condition == ''`) at run time — one of the two acceptable
  outcomes named in the change spec (normalize iff posted closed; else
  stay outdoor).
- **None-safety:** `pull_weather('AZ', '', 999999999)` (bogus game_pk →
  MLB call fails) returned a dict (not None), falling back to Open-Meteo.
- **Schema:** `weather_temperature_f_outdoor` present in `game_context`
  after the idempotent ALTER; table column count 65 → 66.

## References

- `05c_pregame_context.py` — `pull_weather` (fix site) and the weather
  step in `main()` (caller now passes `game_pk`); idempotent ALTER TABLE
  before the `to_sql` append.
- `SCHEMA.py` — regenerated via `generate_schema_doc.py --apply` to pick
  up `weather_temperature_f_outdoor`; `game_context` GOTCHAS updated with
  the dual-temp-columns note and the unposted-roof-state pregame limit.
- `docs/adr/ADR-031-05c-bp-staleness-fallback.md` — proximate
  predecessor; same file, same class of "context field silently carried
  the wrong value," and the same no-backfill forward-only stance.
- `docs/adr/ADR-035-totals-edge-retail-not-sharp.md`,
  Sessions 41-42 (DECISIONS/HISTORY) — the totals over-prediction /
  calibration work this input error sits adjacent to.
- Completed game_pk 825076 — MLB Stats API reference case (condition
  `'Roof Closed'`, temp `'74'`, wind `'0 mph, None'`).

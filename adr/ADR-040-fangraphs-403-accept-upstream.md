# ADR-040: FanGraphs 403 on leaders-legacy.aspx — Accept (Upstream pybaseball), Do Not Fix

**Status:** Accepted
**Date:** 2026-05-31 (Session 40)
**Related:** 05a_fangraphs_enrichment.py (pull functions), 05d weekly refresh
             (step 3 where the 403 surfaced)

## Context / Problem

The FanGraphs enrichment pulls in 05a_fangraphs_enrichment.py —
`pull_fangraphs_pitching` and `pull_fangraphs_batting` — throw HTTP 403 on
`https://www.fangraphs.com/leaders-legacy.aspx`. The failure is recurring
and was seen again in today's 05d run (step 3, FanGraphs refresh).

## Diagnosis (this session, read-only)

The 403 is **upstream in pybaseball, not in our code.**

- 05a never names a FanGraphs endpoint. It imports and calls the library
  functions `pitching_stats(season, season, qual=0)` and
  `batting_stats(season, season, qual=0)` (via the `safe_pull` retry
  wrapper). The `leaders-legacy.aspx` URL, request, and headers are
  constructed entirely inside pybaseball.
- Bare library calls reproduce the identical 403 with **no involvement
  from our code or the database**: both `pitching_stats(2026)` and
  `batting_stats(2026)` raise
  `requests.exceptions.HTTPError: Error accessing
  'https://www.fangraphs.com/leaders-legacy.aspx'. Received status code
  403`. Tracebacks originate in `pybaseball/datasources/fangraphs.py`
  → `html_table_processor.py`.
- Installed pybaseball is **2.2.7, the latest released version**; there is
  no newer release to upgrade into that fixes it.
- As of 2026-05-31, pybaseball is low-maintenance (on the order of ~90
  open issues and ~48 open PRs, merges every few months; fixes for this
  403 class were still unmerged as of Feb 2026), so the upstream-fix
  timeline is open-ended. (Repo stats cited as of this date; do not treat
  as a standing fact.)
- NOT determined this session: whether the 403 is FanGraphs having
  removed/deprecated the legacy page, or anti-scraping blocking
  pybaseball's request signature. Both are upstream of our code; the
  distinction was out of scope.

## Blast radius

FanGraphs data is **cross-validation / research only. It does NOT feed
daily predictions.** Within 05a the FanGraphs pulls run before the
non-critical OAA step, which has its own try/except. The two affected
tables — `fangraphs_pitching` and `fangraphs_batting` (last-known row
counts ~419 and ~818 from the last successful refresh) — are now
**FROZEN / STALE until further notice.** No production prediction path
reads them.

## Decision

**ACCEPT the failure.** Specifically:

- **Do not patch the library.** A local edit to pybaseball is fragile,
  is wiped on reinstall, and the removed-page-vs-anti-scrape-block
  question was not resolved this session.
- **Do not rebuild the pull now.** Bypassing pybaseball to hit the
  current FanGraphs API is real work and is not warranted while the data
  is research-only.

## Known issue (NOT fixed here — flag for later)

The data-freshness report stamps the `fangraphs_*` tables only as "2026"
with no date, which **masks staleness**. These two tables are known-stale
as of 2026-05-31 and must not be treated as current. Making the freshness
report show a real date is a **separate future task**, not done in this
ADR.

## Revisit triggers (either)

1. **FanGraphs cross-validation data is needed live** → scope option 3:
   bypass pybaseball and pull from the current FanGraphs API.
2. **pybaseball ships an upstream release that fixes the leaders-legacy
   403** → re-test a simple version upgrade first, as it would be the
   cheapest fix.

## Consequences

- No code, configuration, or database change is made by this ADR. It is a
  documentation-only decision record.
- Until a revisit trigger fires, 05a's FanGraphs steps are expected to 403
  and are treated as a tolerated, non-blocking failure.

# ADR-025: Voided picks hidden from public dashboard

Status: Accepted
Date: 2026-04-22
Session: 24

## Context

Published picks occasionally get voided after publication. Known reasons
this season:

- **Line movement exceeding threshold** — e.g., Jacob Lopez 4/21 K prop
  published at 4.5, market moved to 5.5 before first pitch. Voided
  operator-side with `game_status='void - line moved 4.5 to 5.5'`.
- **Pregame scratch** — starting pitcher pulled before first pitch
  (Drew Rasmussen 4/7). Voided with `game_status='void'`.

The void convention across trackers is:
- `result_hit` stays NULL (not a win, not a loss)
- `pnl = 0.0` (no money moved)
- `game_status` set to a string starting with the substring 'void'
  (case-insensitive, variable suffix)

Before today, the public dashboard's Yesterday tab rendered voided picks
as cards alongside wins and losses. Two concrete problems:

1. Public readers had no way to know what "void" meant or why a pick
   card showed no W/L outcome. Reading the dashboard as a potential
   subscriber or follower, a void card reads as either a missing result
   or a hidden failure.
2. Voided picks contribute nothing to public P&L, W/L, or edge analysis
   — they're operational noise from the public's point of view.

Today's Lopez 4/21 void would have appeared as a zero-P&L card on the
Yesterday tab next to genuine W/L picks.

## Decision

**Voided picks are excluded from all public dashboard rendering.**

Filter convention applied in `18_generate_dashboard.py` query_resolved
(and any future query that feeds the public dashboard):

```sql
WHERE result_hit IS NOT NULL
  AND (result_hit != -1)
  AND (game_status IS NULL OR LOWER(game_status) NOT LIKE 'void%')
```

The dual check (`result_hit != -1` OR `game_status LIKE 'void%'`) catches
both void markers the system uses:
- `result_hit = -1` — explicit void sentinel (legacy pattern)
- `game_status LIKE 'void%'` — void-with-reason pattern (current convention)

Voided picks remain fully present in the database. They continue to
appear in:
- Operator-facing reports (`21_weekly_validation.py`, with the void
  filter fix from items #7+#8 suppressing their noise but leaving them
  queryable)
- Internal P&L reconciliation
- Audit trails (bet_tracker / totals_tracker / etc. retain the full row
  with status explaining why it was voided)

### Alternatives considered and rejected

**(a) Render voided picks with a visual "VOID" badge.**
Rejected. Adds explanation burden to dashboard UX — the badge itself
needs hover text, a legend, or a separate explainer page. Simpler to
hide them entirely. Internal audit is already served by database rows.

**(b) Show voided picks as neutral-colored cards without result
indicators.**
Rejected. More misleading than helpful: reads as "we bet this, we don't
know if it won," implying operational incompetence. Also creates a
category of cards the public has to learn to interpret.

**(c) Move voided picks to a separate "Housekeeping" section on the
public dashboard.**
Rejected. Adds UI surface area for a case that occurs roughly once per
week. The volume doesn't justify the surface.

## Consequences

### Positive

- Public dashboard shows only picks with real outcomes. No reader has
  to ask "what is a void card?"
- W/L ratios and P&L figures on the dashboard match what a subscriber
  would see reconstructing by hand. No invisible adjustment.
- Internal tracking fully preserved. An operator investigating last
  week's void can still query bet_tracker and see the full record.
- Pattern extensible: future non-standard resolutions (postponements,
  suspended games) can use the same LIKE-based status filter.

### Negative / Caveats

- **Dashboard picks count != tracker rows count for a day that had a
  void.** Anyone cross-checking row-by-row needs to know this. Captured
  here in the ADR; no explicit disclosure on the dashboard itself.

- **A voided pick's absence from the public view is indistinguishable
  from "never published."** If an operator wants to retroactively
  demonstrate that a pick was genuinely published and then voided
  (rather than quietly deleted), the dashboard alone is insufficient —
  the database record is the proof. This is acceptable because the
  project's public narrative is "model's published picks + results,"
  not "every edge considered."

- **Edge case: if `game_status` is set to something void-adjacent but
  not starting with "void" (e.g., "cancelled", "suspended")**, the
  current filter will NOT hide it. These statuses are not currently
  used anywhere in the pipeline; if they appear in the future, this
  filter will need extension.

## Process lessons

1. **Resolution conventions need to be explicit and case-insensitive.**
   The original void filter in resolvers (pre-Session 21) used
   `game_status != 'void'` exact match, which missed
   `'void - line moved 4.5 to 5.5'`. Session 21 fixed resolvers to
   `LOWER(game_status) NOT LIKE 'void%'`. Today's dashboard filter
   follows the same pattern. Any future filter touching `game_status`
   should default to this shape.

2. **Public-facing rendering decisions deserve ADR capture, not just
   code comments.** UI decisions like "hide voids" get revisited when
   a new engineer (or a later version of the same engineer) looks at
   the code six months later and wonders why a filter exists. Without
   this ADR, the temptation to "simplify" by removing the filter would
   be nontrivial.

## Implementation artifacts

Source changes:
- `18_generate_dashboard.py` — `query_resolved` updated to exclude voids
  via the dual check. Commit d59b690 (2026-04-22 morning).

Related fixes (separate items, same session):
- Items #7 and #8: `21_weekly_validation.py` void filter and dedup
  grouping fixes, so internal validation is consistent with the public
  dashboard's void handling.
- Item #12b: pending — renderToday regression verification note for
  the related dashboard early-return bug.

## Verification

Verified 2026-04-22 morning after patch:
- Lopez 4/21 pick (bet_tracker:348, published_picks:81) voided and
  hidden from Yesterday tab.
- Rasmussen 4/7 pick (bet_tracker:140, published_picks:51) already
  voided in an earlier session; confirmed hidden from Yesterday tab.
- All non-voided picks on 4/21 (K 6-5, Totals 6-7, etc.) rendered
  normally.

## References

- ADR-023 — root cause + surface patch discussion, related "silent
  wrong data" category
- ADR-024 — PARK_FACTORS alignment; same session's other decision
- RULES_FOR_CLAUDE.py — Pattern S2 (NULL-unsafe / exact-match SQL
  filters); the same pattern family as the `game_status = 'void'` bug
- Session 24 transcript — Lopez void operation (`20:27:`),
  dashboard patch (morning commit d59b690)

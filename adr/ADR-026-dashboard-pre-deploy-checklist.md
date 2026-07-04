# ADR-026: Dashboard rendering pre-deploy checklist

Status: Accepted
Date: 2026-04-22
Session: 24

## Context

On 2026-04-22 morning, a bug in `docs/index.html`'s `renderToday()`
function caused the watchlist section to silently disappear when
`picks.length === 0`. The function returned early after detecting the
empty picks case, skipping the watchlist render block entirely.

Concrete impact on the day:
- Pregame pipeline produced 0 published picks initially (all 4 tagged
  candidates pending operator review)
- 3 of those candidates got moved to watchlist in morning workflow
- Dashboard pushed with watchlist data embedded
- Watchlist section did not render on public page — appeared as if
  there were no upcoming plays at all
- Discovered on spot-check; patched mid-morning (commit 5f93b84)

The underlying class of bug is common in dashboard JS: a conditional
early-return in one render function skips side-effects (like rendering
a sibling section) that the author mentally grouped as unconditional.
This specific bug is low-stakes (dashboard re-push fixes it), but the
class of bug is insidious — other render branches could fail silently
in the same way without detection.

The project has no JS test harness. Adding one for a single render
function is disproportionate: a ~20-line testing infrastructure would
dwarf the ~200-line file it tests, and new bugs tend to be in
never-tested paths regardless of framework presence.

## Decision

**Add a pre-deploy manual verification checklist for dashboard pushes,
plus an inline comment at the relevant early-return site.**

### Inline comment (code-level hazard marker)

In `docs/index.html`, at the top of `renderToday()` after the empty
picks check, add:

```js
// NOTE: do not return early here. Watchlist section must still render
// even when picks.length === 0. The 2026-04-22 regression (commit
// 5f93b84) was an early-return that skipped the watchlist block.
```

This comment lives at the specific hazard site. Future editors who
look at the code and think "why is this so convoluted, let me
simplify" see the warning before touching it.

### Pre-deploy manual verification checklist

Before any `push_with_watchlist.py` run:

1. **Picks-only render:** picks=3+, watchlist=0 → Today tab shows picks,
   no watchlist section. (Normal case.)
2. **Watchlist-only render:** picks=0, watchlist=2+ → Today tab shows
   the watchlist section, no "No picks today" message that implies
   empty. (Was broken before 5f93b84; the specific case that regressed.)
3. **Mixed render:** picks=2, watchlist=2 → Today tab shows both
   sections with clear visual separation.
4. **Both empty:** picks=0, watchlist=0 → Today tab shows "No picks
   today yet" or similar neutral message, not a broken layout.

For a scheduled deploy, the operator opens the dashboard in private
browsing (bypasses cache) and visually confirms the tab for the day's
specific scenario. This takes under 30 seconds per push.

### Alternatives considered and rejected

**(a) JavaScript unit tests for render functions (jest, vitest, etc.).**
Rejected. Adds a test runner, node build step, and a dependency tree
to a project that otherwise builds zero JS and has no package.json.
The cost of the infrastructure exceeds the bug volume justifying it.

**(b) Rewrite renderToday() to be side-effect-only at the caller's
orchestration level** (i.e., refactor so the empty-picks branch
cannot skip sibling rendering by construction).
Considered. Cleaner in principle. Rejected for now because the
current structure is shared across renderToday, renderYesterday,
and a few other tab renderers; refactoring for this one case would
leave inconsistent patterns, and refactoring all of them is a
separate project.

**(c) Pre-deploy automated smoke test that curls the deployed page
and greps for expected substrings.**
Considered. Actionable as a future enhancement — a ~20-line Python
script could fetch the dashboard after push and assert on section
presence. Worth revisiting when the dashboard has more sections or
when manual checks start getting skipped. Deferred.

## Consequences

### Positive

- The specific bug that caused today's breakage is marked at the
  hazard site. A reader editing the function can't miss the warning.
- Four concrete pre-deploy scenarios are captured. An operator
  inherits explicit test cases rather than having to improvise.
- Zero infrastructure added. No build step, no CI, no new dependency.

### Negative / Caveats

- **Manual checklist is an honor-system safeguard.** If the operator
  skips the check before a push, the bug can recur. This is acceptable
  tradeoff for a single-person operational project where the operator
  IS the engineer and can self-evaluate when the risk is worth the
  time.

- **The inline comment is not enforced.** A future refactor could
  remove or relocate the comment without fixing the underlying
  hazard. This is the same risk as any code comment. Partial
  mitigation: the ADR links the comment to a specific session and
  commit, so its provenance is auditable.

- **The checklist covers renderToday, not other renderers.** If the
  same bug class appears in renderYesterday, renderSettled, or a
  future tab, it will not be caught by this checklist. Captured as
  a known gap. If a similar regression occurs in another renderer,
  the checklist should be extended.

## Process lessons

1. **Early returns in side-effect-laden render functions are a bug
   pattern, not a coding style.** Any function that renders multiple
   independent page sections should either (a) not have early returns
   based on one section's data, or (b) put each section's render into
   its own function so the orchestrator can skip selectively. The
   current code mixes both patterns; the inline comment is a
   stopgap until a proper refactor.

2. **Missing-test infrastructure is not the same as needs-test
   infrastructure.** For a single engineer project with low-volume
   deploys and visual-inspection-cheap verification, a checklist
   beats a test harness. The rule: add testing infrastructure when
   the cost of checking manually exceeds the cost of maintaining the
   harness. Not before.

3. **"We caught this in spot-check" is not a robust discovery
   mechanism.** Today's bug was discovered because PJK looked at the
   dashboard. If the bug had happened on a day PJK didn't visit the
   public-facing URL, it could have persisted for a day or more. The
   pre-deploy checklist moves verification into the normal push
   workflow rather than relying on post-deploy incidental browsing.

## Implementation artifacts

Code-level change:
- `docs/index.html` — inline comment at renderToday early-return site
  (to be added separately; this ADR establishes the pattern).

The dashboard fix itself was already deployed earlier today (commit
5f93b84). This ADR captures the learnings and prevention measures, not
the fix.

## Verification

Verified 2026-04-22:
- Today's 3-picks/0-watchlist scenario rendered correctly after fix
  5f93b84 (morning verification).
- Inline comment to be added in a follow-up commit; not yet
  deployed.
- Checklist committed here. First use at tomorrow morning's deploy.

## References

- Dashboard repo commit 5f93b84 — the actual fix (2026-04-22 ~11:34)
- ADR-025 — void display policy (same session, related dashboard work)
- Session 24 transcript — dashboard investigation and patch
  (`11:34` timestamp), workflow discussion (`12:00` area)

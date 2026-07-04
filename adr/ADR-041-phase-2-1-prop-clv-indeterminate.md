# ADR-041: Phase 2.1 Prop Closing-Line Value (K + Outs) -- INDETERMINATE Both Markets

**Status:** Accepted
**Date:** 2026-05-31 (Session 40)
**Pre-registration:** PHASE_2_1_PREREG_001.py v1.1 LOCKED 2026-05-31
**Related:** ADR-035 (totals edge vs retail not sharp), ADR-038 (Phase 1.9a
             INDETERMINATE), ADR-039 (low-tier REJECTED / wRC+ closed),
             ADR-040 (FanGraphs 403 accepted)

## Context

The 2026 K-prop and pitcher-outs published picks are in drawdown. Phase 2.1
tested whether that is edge decay or variance, via closing-line value (CLV) of
our logged entry line against the SAME retail book's closing line. No sharp
prop anchor exists (Pinnacle does not carry these markets), so the comparison
is necessarily vs retail close. 2026-only: both prop trackers begin in 2026, so
no pre-2026 prop comparison is possible. Pre-reg PHASE_2_1_PREREG_001.py v1.1
(LOCKED 2026-05-31) was pilot-gated; the 2026-05-30 pilot passed at 98.2% join.

## Backfill

783 of 793 in-scope events on 59 pick-dates (10 events returned HTTP 404 at
their snapshot and were not pulled). Region us, markets pitcher_strikeouts +
pitcher_outs, closing snapshot = latest snapshot_time_utc < commence_time per
event. Incremental per-event fsync'd checkpointing; files only (mlb_model.db
never opened). Cost: 15,379 credits actual vs 15,919 estimate (540 under).
Balance 96,410 -> 81,031.

## Decision / Verdict

INDETERMINATE for both markets (line-based CLV, bootstrap seed 42 / 10k, K and
outs separately; CI-crossing-zero forces non-ACCEPT per Section 5):

| Hypothesis | Market | n | mean line-CLV | 95% CI | floor | Verdict |
|---|---|---|---|---|---|---|
| H1_K | pitcher_strikeouts | 771 | -0.0039 K | [-0.0233, +0.0156] | 0.10 | INDETERMINATE |
| H1_O | pitcher_outs | 1046 | +0.0110 outs | [-0.0091, +0.0315] | 0.15 | INDETERMINATE |

Both CIs straddle zero; |mean CLV| is ~1/26 of the floor (K) and ~1/14 (outs).
No measurable CLV in either direction -- entries land essentially AT the
same-book close. Drops (post-fix): 103 pitcher_not_found_at_book (book had no
closing line for that pitcher/market/side, incl. the 10 un-pulled 404 events).
Reconciles: 771 + 1046 matched + 103 drops = 1920 picks.

## Interpretation (factual, no overclaim)

- The prop drawdown is NOT explained by poor closing-line value: entries are
  fair-priced vs the close, not systematically beaten by it.
- CLV cannot distinguish edge decay from variance at this n (near-zero CLV, CI
  crosses zero). Absence of positive CLV is weak evidence against a live edge
  but does NOT earn an ACCEPT-decay verdict.
- The K/outs drawdown remains FORMALLY UNEXPLAINED by this test.
- Outcome matrix (C): no publish-state change; do NOT pull more snapshots;
  document and stop. Section 6 commitments honored (no threshold relaxation, no
  dropping the worse market, no redefining CLV, no extra-snapshot pulling).

## Honesty boundaries

- CLV vs RETAIL close (books we bet), NOT vs sharp (no sharp prop anchor).
- Baseline is the MIDDAY-LOGGED line (logged_at ~12:56), not an executed price.
- 2026-only; no pre-2026 prop history, so no historical prop CLV comparison.

## Bug caught and fixed (disclosed; verdict-neutral)

The v1.1 period-stripping (added for pitcher names) leaked into book-name
lookup via the shared normalizer: n11('BetOnline.ag') = 'betonlineag' but the
BOOKMAP key was still 'betonline.ag', so ~69 BetOnline.ag picks were wrongly
dropped as book_unmapped. One-line BOOKMAP fix ('betonline.ag' ->
'betonlineag'); re-analyzed on the EXISTING raw data (no new pull, no credits).
Recovered 65 picks to matches (3 K + 62 outs) and 4 to pitcher_not_found; drops
168 -> 103. Verdict IDENTICAL before and after the fix (INDETERMINATE both) --
robust. Conformance fix to the locked same-book rule, not a verdict-rescue.

## Artifacts (durable files; live DB untouched)

E:\mlb_model\phase_2_1_out\: phase_2_1_results.csv, phase_2_1_clv_rows.csv,
phase_2_1_drops.csv, phase_2_1_raw_lines.jsonl (783 events),
phase_2_1_events_done.txt, phase_2_1_run.log.

## Consequences

- No publish-rule change. Prop tags continue per existing rules.
- Adds an INDETERMINATE to the drawdown root-cause tally (14th across Sessions
  34-40). FanGraphs 403 (ADR-040) is an infrastructure accept, not a drawdown
  root cause, and is not counted in that tally.
- Documentation only; no database or pull affected. The sole code change is the
  disclosed one-line BOOKMAP fix in phase_2_1_execute.py.

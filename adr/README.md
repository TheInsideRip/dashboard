# Architecture Decision Records

One-decision-per-file log for The Inside Rip. Each ADR captures a
single decision with its context, alternatives considered,
decision rationale, and consequences. Once accepted, ADRs are
immutable — a changed decision gets a new ADR that supersedes
the old one.

## Index

| # | Title | Status | Date |
|---|-------|--------|------|
| 057 | [Filter E live parent-exact rebuild blocked; confirmed-lineup is proxy-only](ADR-057-filter-e-live-parent-exact-blocked.md) | Accepted | 2026-06-20 |
| 045 | [v2 substrate serving cutover (betting path)](ADR-045-v2-substrate-serving-cutover.md) | Accepted | 2026-06-07 |
| 044 | [OUTS_UNDER demotes on corrected (v2) substrate — edge was largely contamination](ADR-044-outs-under-demote-on-v2-substrate.md) | Accepted | 2026-06-07 |
| 043 | [substrate v2 not wired — live contamination confirmed](ADR-043-substrate-v2-not-wired-live-contamination.md) | Accepted | 2026-06-07 |
| 042 | [05c closed-roof temperature normalization — outdoor temp poisoned dome totals](ADR-042-05c-roof-temperature-normalization.md) | Accepted | 2026-06-05 |
| 024 | [PARK_FACTORS alignment between live tagger and research substrate](ADR-024-park-factors-alignment.md) | Accepted | 2026-04-21 |
| 023 | [Outs pipeline team-swap bug — root cause and fix](ADR-023-outs-team-swap-root-cause.md) | Accepted | 2026-04-20 |

## Conventions

- Filename: `ADR-NNN-<slug>.md`, sequential numbering, no reuse.
- Status: Proposed / Accepted / Deprecated / Superseded by ADR-XXX
- Sections: Context, Decision, Alternatives considered, Consequences,
  Process lessons (if any), References
- Write at decision time, not weeks after

Prior decisions from before this log was established are captured
in `DECISIONS.py` at project root; new decisions from ADR-023
onward live here.

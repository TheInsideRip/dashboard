# ADR-054 (Accepted): Last-start recency deviation does not beat the K line; the K market is efficient at consensus juice

Status: **Accepted** (2026-06-16). READ-ONLY study; no serving/builder/tagger code changed, no DB
writes.
Relates to: ADR-053 (whiff -- the other independent K angle, also real-but-sub-juice), ADR-048
(K stays dark -- reinforced), ADR-052 (detection floor -- the bet test uses the recalibrated
protocol, so this is not a floor artifact).

> Figures attributed to diag_laststart_dev_vs_kline_20260616.py output
> (laststart_dev_vs_kline_OUT.txt), 2026-06-16. Leakage and the as-of nature of the baseline
> were verified first-hand this run.

## What was tested
Whether a starter's last-outing deviation from his own norm (in RATE terms, not raw K count)
predicts his NEXT start vs the K consensus line -- i.e. does the book mis-weight recency? Signal:
last_start_dev = (prior start actual_ks / actual_bf) - baseline, where baseline = `cum_k_pct`
ENTERING the prior start (career cumulative, verified as-of / leakage-safe: a game's outcome only
moves the NEXT row's cum_k_pct). Direction (fade vs ride) locked on 2024 discovery, confirmed on
2025 holdout + both halves. Strict as-of; prior.game_date < scored.game_date asserted (0 violations
over 8,252 scored rows).

## Result (per study output, 2026-06-16)
- A real effect exists but is FADE / mild mean-reversion (TRAIN corr(dev, actual - line) = -0.048)
  -- and it is **smaller than the vig**.
- The tail strategy (in the discovered direction) **loses on TRAIN (-1.5%), TEST (-4.0%), and both
  2025 halves**, and is negative across all baseline `cum_k_pct` bands (so it is not a hidden
  pitcher-quality artifact), all `predicted_ks` bands, and all line-staleness bands.
- UNDER breakeven 0.543 (median -119 juice) is the wall. Not bettable.

## Combined verdict with ADR-053
Two INDEPENDENT K angles -- arsenal matchup (ADR-053) and last-start recency (this ADR) -- are both
real-but-sub-juice. That points to **the K consensus line being hard, not the signals being soft**.
K stays dark (reinforces ADR-048). Data limit: K props exist 2024-03-28 .. 2025-09-28 only -- one
discovery season (2024) + one holdout season (2025); no 2023/2026 K lines for out-of-period
confirmation.

# ADR-052 (Accepted): The edge-test method has a detection floor (~0.545 WR / +4% ROI); campaign "nulls" mean "no FAT edge," not "no edge"

Status: **Accepted** (2026-06-16). READ-ONLY method-validation study; no serving/builder/tagger
code changed, no DB writes.
Relates to: ADR-035/041 (totals/prop edge verdicts), ADR-048 (K drawdown H_NULL), ADR-051
(totals leakage -- clean hunts null), and every prior campaign "null" verdict (reframed below).

> Figures below are attributed to diag_method_validation_injection_20260616.py output
> (method_validation_injection_OUT.txt), 2026-06-16. The method's no-false-positive behavior
> and the floor location are the durable, reusable facts.

## What was tested
An injection / recovery test (per diag_method_validation_injection_20260616.py): planted known
win-rates {0.58, 0.55, 0.54, 0.53, 0.525, 0.50} into the real game structure via a neutral
game_pk-hash slice, then rediscovered them through the EXACT production edge-test pipeline,
alongside 60 noise cells, across 5 seeds.

## Results (per study output, 2026-06-16)
- The true null (p=0.50) was detected 0/5; the 60 noise cells produced 0/60 -- **NO false
  positives**. Campaign nulls are real, not fabricated by a leaky test.
- **Detection floor ~0.55 WR** at a ~420-game holdout cell; planted 0.53-0.54 edges were detected
  <= 1/5.
- The **binding constraint is the ROI >= +4% bar, NOT the holdout split**: at -110, WR 0.54 =
  +3.1% ROI < +4%, so a genuine 54% edge fails the bar at infinite n. The floor scales with cell
  n (~0.535 at n~1000; ~0.60+ at n~100).

## Durable reframe (the point of this ADR)
Every prior and future campaign "null" should be read as **"no edge of >= ~0.545 WR / +4% ROI
survives,"** NOT "no edge at all." The hunts ruled out FAT edges; they did not rule out grindable
52-54% edges, which sit below the bar. Recalibrated hunts therefore use a breakeven-plus bar
(ROI >= +1.5% at ACTUAL juice) WITH compensating noise controls: large-n pooling (terciles/
quintiles, not thin deciles), 2024->2025 holdout split further by both 2025 halves, dose-response
gradient, residual control within model/line bands, and a multiple-comparisons funnel. (The
recalibrated whiff and last-start hunts -- ADR-053/054 -- used exactly this protocol and still
found no bettable K edge, so the K verdict is not a floor artifact.)

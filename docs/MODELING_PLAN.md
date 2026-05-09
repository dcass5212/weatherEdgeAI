# Modeling Plan

## Purpose

This document defines how WeatherEdge AI should estimate probabilities, evaluate model quality, and communicate uncertainty. The goal is not to look sophisticated prematurely; the goal is to produce a defensible, testable modeling pipeline that can improve over time.

## V1 Modeling Scope

V1 focuses on precipitation threshold markets.

Supported target shape:

```text
Will {location} receive {operator} {threshold} {unit} of rain during {target window}?
```

Initial examples:

- Will New York City get more than 1 inch of rain on May 5?
- Will Chicago receive at least 0.5 inches of rain tomorrow?
- Will NYC have less than 2 inches of precipitation in May?
- Will Hong Kong have 240mm or more of precipitation in May?

The current parser and baseline model support one-sided precipitation thresholds: `>`, `>=`, `<`, and `<=`, with inch and millimeter thresholds. Interval contracts such as `between 2 and 3 inches` remain out of scope until an interval probability model is added.

## Current Baseline

Current model version:

```text
baseline_precip_v1
```

Inputs:

- Parsed precipitation threshold.
- Parsed operator.
- Forecast precipitation total.
- Forecast precipitation unit.
- Target window from the parsed market and forecast snapshot.

Current behavior:

- If forecast precipitation is missing, return `p_yes = 0.5` with low confidence.
- If the forecast is meaningfully on the YES side of the threshold, increase YES probability.
- If the forecast is meaningfully on the NO side of the threshold, decrease YES probability.
- Keep probabilities bounded between 0 and 1.

Current probability bands:

- Forecast at least 0.5 units on the YES side of the threshold: `p_yes = 0.75`.
- Forecast 0.1 to 0.5 units on the YES side of the threshold: `p_yes = 0.60`.
- Forecast within 0.1 units of the threshold: `p_yes = 0.50`.
- Forecast 0.1 to 0.5 units on the NO side of the threshold: `p_yes = 0.40`.
- Forecast more than 0.5 units on the NO side of the threshold: `p_yes = 0.25`.

Purpose:

- Establish an end-to-end prediction pipeline.
- Provide a baseline for later model comparisons.
- Keep behavior easy to explain in interviews.

## Feature Roadmap

Near-term features:

- Forecast precipitation total.
- Threshold value.
- Difference between forecast and threshold.
- Ratio of forecast to threshold.
- Operator.
- Time until target window.
- Forecast lead time.
- Forecast source.
- Location.

Medium-term features:

- Forecast precipitation probability if available.
- Daily forecast distribution or hourly totals.
- Weather alert signals.
- Recent precipitation history.
- Historical forecast error by location.
- Market liquidity and spread.
- Market price movement.
- Time until market close.

Future features:

- NOAA/NWS observed outcomes.
- Historical forecast revisions.
- Seasonal and regional calibration features.
- Ensemble weather model features if available.

## Model Roadmap

### Stage 1: Transparent Baseline

Use the current deterministic probability bands.

Done when:

- Predictions are stored with model version and features.
- Tests cover probability behavior.
- API workflow can produce predictions end to end.

### Stage 2: Calibrated Heuristic

Improve the baseline with smoother probability curves.

Possible approach:

- Use a logistic curve around the threshold difference.
- Tune curve parameters from historical outcomes.
- Adjust confidence based on lead time and missing features.

Done when:

- The heuristic improves calibration versus `baseline_precip_v1`.
- Model assumptions are documented.
- Backtest output compares both versions.

### Stage 3: Trained Model

Train a simple supervised model after enough resolved records exist.

Candidate models:

- Logistic regression.
- Calibrated gradient boosting.
- Random forest as a benchmark, if explainability remains acceptable.

Done when:

- Train/test split methodology is documented.
- Leakage risks are addressed.
- Calibration is measured.
- The model beats the baseline on useful metrics.

## Evaluation Metrics

Primary metrics:

- Brier score: measures squared probability error.
- Log loss: penalizes overconfident wrong predictions.
- Calibration buckets: compare predicted probabilities with observed outcomes.

Secondary metrics:

- Prediction count.
- Coverage by parser success rate.
- Average edge identified.
- Paper-trading ROI.
- Max drawdown for paper trades.
- Recommendation hit rate by bucket.

## Paper Strategy Sizing

Current EV recommendations use a simple paper-mode sizing rule:

- Only actionable positive edges receive a suggested size.
- Size equals edge percentage points, capped at 10 simulated units.
- A 3.5 percentage-point edge suggests 3.5 units.
- A 31 percentage-point edge is capped at 10 units.

This exists to make paper-trading records deterministic and reviewable. It is not a live-execution risk model and should not be presented as evidence of trading performance.

Avoid overemphasizing:

- Raw accuracy without probability context.
- Profit claims without enough data.
- Single backtest results without calibration and sample-size discussion.

## Calibration Plan

Predictions should be grouped into buckets, such as:

- 0.00 to 0.20
- 0.20 to 0.40
- 0.40 to 0.60
- 0.60 to 0.80
- 0.80 to 1.00

For each bucket, report:

- Number of predictions.
- Average predicted probability.
- Observed YES rate.
- Calibration gap.

Interpretation:

- A bucket with average prediction 0.70 should resolve YES about 70% of the time over enough examples.
- Small sample sizes should be called out directly.

## Backtesting Requirements

See `BACKTESTING_SPEC.md` for the implementation-level replay and reporting specification.

A useful backtest needs:

- Stored predictions.
- Stored forecast snapshots used by those predictions.
- Stored market prices used for EV recommendations.
- Resolved outcomes.
- A clear evaluation period.
- A fixed model version.

Backtest reports should include:

- Model version.
- Evaluation window.
- Number of predictions.
- Win rate.
- Brier score.
- Log loss.
- Calibration summary.
- Sample-size note.
- Paper-trade count.
- Paper ROI.
- Max drawdown.
- Paper PnL.
- Notes on sample-size limitations. Initial backtest responses include this as `sample_size_note`.

## Modeling Guardrails

- Do not present probabilities as certainty.
- Do not claim profitability without evidence.
- Do not optimize to paper ROI alone.
- Do not train models on data that would not have been available at prediction time.
- Do not mix live-trading execution logic into modeling code.
- Do not use model outputs for live execution until paper trading, backtesting, and safety gates exist.
- Preserve model version and feature payload for every prediction.

## Portfolio Story

The strongest interview story is:

1. Start with a transparent baseline.
2. Build the data pipeline needed to evaluate it.
3. Measure calibration and error.
4. Improve the model only when data supports it.
5. Keep paper trading available and separate from any future live execution records.

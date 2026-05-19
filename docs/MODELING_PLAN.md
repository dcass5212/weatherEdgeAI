# Modeling Plan

## Purpose

This document defines how WeatherEdge AI should estimate probabilities, evaluate model quality, and communicate uncertainty. The goal is not to look sophisticated prematurely; the goal is to produce a defensible, testable modeling pipeline that can improve over time.

## V1 Modeling Scope

V1 focuses on precipitation threshold markets and now includes first-pass daily high/low temperature bucket support.

Supported target shape:

```text
Will {location} receive {operator} {threshold} {unit} of rain during {target window}?
```

Initial examples:

- Will New York City get more than 1 inch of rain on May 5?
- Will Chicago receive at least 0.5 inches of rain tomorrow?
- Will NYC have less than 2 inches of precipitation in May?
- Will Hong Kong have 240mm or more of precipitation in May?
- Will Hong Kong have between 190-200mm of precipitation in May?

The current parser and baseline model support one-sided precipitation thresholds: `>`, `>=`, `<`, and `<=`, with inch and millimeter thresholds. Interval contracts such as `between 2 and 3 inches` are available only behind an explicit experimental toggle for paper-runner research; they should not be treated as a proven model improvement.
The parser extracts target windows for daily wording such as `tomorrow` and `on May 5`, plus month windows such as `in May`, because observed-outcome resolution and trade settlement require a completed target window.

Temperature examples:

- Highest temperature in NYC on May 17 80-81F?
- Lowest temperature in London on May 17 10C or lower?

Temperature buckets are represented as binary contracts over a range or threshold. They are early paper-research signals, not trained or calibrated evidence.

## Implemented Models

Default model version:

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
- If an enabled interval contract's forecast total falls inside the interval, return a modest YES probability with low confidence; outside the interval, reduce YES probability based on distance from the range.
- Keep probabilities bounded between 0 and 1.

Current probability bands:

- Forecast at least 0.5 units on the YES side of the threshold: `p_yes = 0.75`.
- Forecast 0.1 to 0.5 units on the YES side of the threshold: `p_yes = 0.60`.
- Forecast within 0.1 units of the threshold: `p_yes = 0.50`.
- Forecast 0.1 to 0.5 units on the NO side of the threshold: `p_yes = 0.40`.
- Forecast more than 0.5 units on the NO side of the threshold: `p_yes = 0.25`.
- Enabled interval contract, forecast inside the range: `p_yes = 0.65`.
- Enabled interval contract, forecast outside but near the range: `p_yes = 0.35`.
- Enabled interval contract, forecast far outside the range: `p_yes = 0.20`.

Purpose:

- Establish an end-to-end prediction pipeline.
- Provide a baseline for later model comparisons.
- Keep behavior easy to explain in interviews.

Additional implemented model version:

```text
baseline_temperature_bucket_v1
```

Current behavior:

- Uses the parsed `temperature_kind` (`high` or `low`) to select forecast daily max or min temperature.
- Converts Celsius and Fahrenheit when the forecast unit differs from the parsed market unit.
- Gives modest YES probability when the point forecast falls inside a bucket range.
- Reduces YES probability as the point forecast moves away from the bucket.
- Supports simple `between`, `>=`, `<=`, and exact-temperature shapes.

Limitations:

- Uses a point forecast only; it does not yet model a full temperature distribution.
- It is not trained or calibrated.
- Observed temperature outcome resolution is still future work, so evidence reports should not treat this model as proven.

Additional implemented model version:

```text
logistic_precip_v1
```

Current behavior:

- Uses a fixed-coefficient logistic regression formula over explicit precipitation features.
- Computes a YES-side margin between forecast precipitation and the parsed threshold.
- Converts inch and millimeter thresholds when forecast and parsed threshold units differ.
- Stores feature payload fields including normalized threshold, margin, margin ratio, logit, model family, and coefficient source.
- Supports the same one-sided operators as the baseline and the opt-in interval-contract shape.
- Is selectable through `POST /predictions/run/{market_id}?model_version=logistic_precip_v1`, the paper-runner API request field, and the paper-runner CLI `--model-version logistic_precip_v1`.

Limitations:

- The current coefficients are hand-selected initial coefficients, not trained coefficients.
- This model should be treated as a smoother comparison candidate against `baseline_precip_v1`, not as evidence of improved trading performance.
- Promotion requires resolved-outcome evaluation across Brier score, log loss, calibration, market-implied comparisons, coverage, and paper-run evidence.

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

- A first fixed-coefficient logistic version exists. Implemented as `logistic_precip_v1`.
- The heuristic improves calibration versus `baseline_precip_v1`. Not yet proven.
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

## Algorithm Refinement Loop

Use paper trading as a data-collection and validation system, not as proof of live-trading readiness by itself.

1. Collect broad signals through rehearsals and dry runs before increasing simulated exposure. Candidate predictions and EV recommendations are useful even when no paper trade is opened.
2. Increase paper-trade limits gradually and document the caps used for each run. Paper PnL is only interpretable when exposure, liquidity, spread, duplicate-trade, and location limits are known.
3. Train or tune future models on all evaluated recommendations and resolved outcomes, including skipped candidates. Opened paper trades alone are a biased sample because they already passed the current trade-selection rules.
4. Keep research datasets separate from paper portfolio results. Research datasets answer which features predict outcomes; paper portfolio results answer whether a constrained strategy would have behaved reasonably.
5. Promote a model or selection rule only after scheduled outcome resolution shows improvement against the baseline on calibration, Brier score, log loss, market-implied comparisons, coverage, and unresolved-trade diagnostics.

This loop is required before treating any upgraded model as a candidate for eventual live trading. Live execution still requires separate safety controls, audit logs, risk limits, and tests proving paper mode cannot place live orders.

## Backtesting Requirements

See `BACKTESTING_SPEC.md` for the implementation-level replay and reporting specification.
See `MODEL_TRAINING_WORKFLOW.md` for the step-by-step process from a frozen
baseline read to a trained logistic regression model.

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
- Paper settlement cost assumptions, including fee and slippage rates. Implemented as `paper_fee_rate` and `paper_slippage_rate` request fields with zero-cost defaults, and reported as gross PnL, fee cost, slippage cost, net PnL, ROI, and a settlement note.
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

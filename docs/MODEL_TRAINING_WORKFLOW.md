# Model Training Workflow

## Purpose

This document describes the path from a baseline model read to a trained
logistic regression model. The goal is to improve probability quality with
evidence, not to replace the baseline just because a smoother model exists.

Paper trading remains the default execution mode throughout this workflow. Model
research must not introduce live trading, authenticated order placement, wallet
signing, or live position management.

## Model Roles

`baseline_precip_v1` is the benchmark model. It should remain frozen unless there
is a deliberate version bump. Its value is that it is transparent, stable, and
easy to debug.

`logistic_precip_v1` is the first smoother comparison model. It currently uses
fixed, hand-selected coefficients over forecast-vs-threshold features. It is not
trained yet and should not be presented as evidence of better performance.

A trained model should use a new version name, such as
`logistic_precip_trained_v1`. Do not mutate historical model behavior under an
existing model version.

## Phase 1: Freeze The Baseline

Keep `baseline_precip_v1` unchanged while collecting and evaluating records.
Future model versions should be compared against this fixed benchmark.

The baseline read should answer:

- How many predictions were evaluated?
- What were the Brier score and log loss?
- How did the calibration buckets look?
- How much market-implied comparison coverage existed?
- How many records were excluded because outcomes were missing?
- How did paper trades settle under the documented fee and slippage assumptions?

## Phase 2: Collect Baseline Predictions

Run baseline rehearsals to estimate workflow coverage without creating simulated
trades:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --rehearsal --model-version baseline_precip_v1
```

Run baseline paper passes when you want simulated trades:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --model-version baseline_precip_v1
```

For longer validation, use bounded loop mode:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --interval-minutes 30 --max-hours 10 --model-version baseline_precip_v1
```

Keep the runner's price, freshness, spread, liquidity, and paper portfolio
limits in the run record. Those settings are part of the evidence context.

## Phase 3: Wait For Target Windows To Complete

Do not evaluate weather markets before their target weather windows complete.
Daily markets can usually be resolved soon after the target date. Monthly
precipitation markets need the full month to finish.

Predictions made after a target window has started are not equivalent to
forecast-only pre-event predictions. The current paper runner skips started or
elapsed windows for that reason.

## Phase 4: Resolve Outcomes

After target windows complete, resolve eligible outcomes and settle matching
open paper trades:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\research_maintenance.py --start-date 2026-05-01 --end-date 2026-05-10 --limit 100
```

Use the eligibility preview when you want to inspect readiness without provider
calls or writes:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/backtests/resolved-outcomes/eligibility-preview?resolution_provider=open_meteo_archive&limit=100"
```

Outcome records should preserve the resolution provider and raw payload so later
evaluation can trace where the observed weather value came from.

## Phase 5: Run The Baseline Backtest

Run a persisted backtest for the fixed baseline model:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/backtests/run `
  -ContentType "application/json" `
  -Body '{"start_date":"2026-05-01","end_date":"2026-05-10","model_version":"baseline_precip_v1"}'
```

Review:

- `num_predictions`
- `coverage_diagnostics`
- `baseline_comparisons`
- `brier_score`
- `log_loss`
- `calibration_buckets`
- `sample_size_gate`
- `paper_total_pnl`
- `paper_roi`
- `max_drawdown`
- `paper_settlement_note`

Small samples are not enough to claim model quality. Use them first to verify
that replay, resolution, and calibration workflows are functioning.

## Phase 6: Generate A Baseline Evidence Report

Use the evidence report to combine runner history, record counts, backtest
metrics, paper-trade lifecycle counts, market-implied coverage, and
interpretation limits:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/evaluation/evidence-report?start_date=2026-05-01&end_date=2026-05-10&model_version=baseline_precip_v1"
```

Store or copy the important metrics into research notes before changing model
logic. The baseline read is the comparison point for all later work.

## Phase 7: Build A Training Dataset

Training rows should come from evaluated predictions joined to resolved
outcomes. Use all evaluated predictions or recommendations, not only opened
paper trades. Opened trades are biased because they already passed liquidity,
spread, duplicate-trade, and portfolio-limit filters.

Initial feature candidates:

- Forecast precipitation total.
- Parsed threshold value normalized into forecast units.
- YES-side forecast margin.
- Margin ratio.
- Operator indicator, such as greater-than versus less-than.
- Forecast lead time.
- Forecast source.
- Location or region, only if there is enough data to avoid overfitting.
- Market YES price, liquidity, and spread for comparison or later strategy
  models, not for weather-outcome modeling unless the research question
  explicitly includes market information.

Target:

```text
actual_outcome == YES
```

Training rows must include only information available at prediction time. Do not
use observed weather, final market resolution data, or any post-event fields as
features.

## Phase 8: Train Logistic Regression Offline

Train a simple logistic regression on the resolved dataset. Start with a narrow
feature set:

- Margin ratio.
- Log threshold.
- Operator indicator.
- Forecast lead time.

Use time-aware evaluation where possible. If the dataset is small, prefer a
clear holdout period or rolling split over random splits that can hide temporal
leakage.

Record:

- Training window.
- Validation window.
- Feature list.
- Coefficients.
- Intercept.
- Regularization settings.
- Sample counts.
- Brier score.
- Log loss.
- Calibration buckets.
- Comparison against `baseline_precip_v1`, `logistic_precip_v1`, always-50%,
  and market-implied probability where available.

## Phase 9: Add A Trained Model Version

Add a new model version instead of changing an existing one:

```text
logistic_precip_trained_v1
```

The implementation should:

- Store explicit coefficients or load a versioned artifact.
- Preserve `model_version` on every prediction.
- Store the feature payload used for each prediction.
- Keep the baseline and fixed-coefficient logistic models available.
- Add focused tests for feature construction, coefficient application, and API
  model selection.

If a model artifact is introduced, keep it versioned, deterministic, and
reviewable. Do not depend on live training during API requests.

## Phase 10: Replay And Compare

Generate predictions with the trained model and evaluate the same date window:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/backtests/run `
  -ContentType "application/json" `
  -Body '{"start_date":"2026-05-01","end_date":"2026-05-10","model_version":"logistic_precip_trained_v1"}'
```

Compare against:

- `baseline_precip_v1`
- `logistic_precip_v1`
- Always-50%
- Market-implied probability, when linked market prices exist

Use the same outcome window and cost assumptions when comparing paper results.

## Promotion Criteria

Do not promote the trained logistic model based on one attractive metric.

A candidate model should improve or hold steady against the baseline on:

- Brier score.
- Log loss.
- Calibration buckets.
- Market-implied comparison where coverage exists.
- Coverage diagnostics.
- Sample-size gate.
- Paper-trade lifecycle and unresolved-trade diagnostics.

A model should not be promoted if:

- The sample is too small to interpret.
- Improvement comes only from opened paper trades.
- Calibration worsens materially.
- The feature set includes leakage.
- Outcome coverage is too sparse or biased.
- The model performs worse than the baseline on core probability metrics.

## Documentation Checklist

When a trained model is added or promoted, update:

- `README.md` for model usage.
- `docs/MODELING_PLAN.md` for assumptions, features, and limitations.
- `docs/BACKTESTING_SPEC.md` for replay expectations if they change.
- `docs/API_WORKFLOWS.md` for API usage.
- `docs/ROADMAP.md` for current priorities and status.
- `CHANGELOG.md` for the implementation prompt.

Keep implemented behavior separate from planned behavior. Do not claim trading
performance without resolved-outcome and paper-trading evidence.

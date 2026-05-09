# Backtesting Spec

## Purpose

Backtesting should show whether model probabilities and strategy recommendations have evidence behind them. It should not be used to claim profitability without sample-size context and calibration results.

## Required Data

A meaningful backtest needs:

- Stored markets.
- Parsed markets.
- Market price snapshots.
- Weather forecast snapshots.
- Predictions with model version and feature payload.
- EV recommendations.
- Paper trades when evaluating strategy behavior.
- Resolved outcomes.

## Resolved Outcomes

Resolved outcomes should capture:

- Market ID.
- Actual YES/NO outcome.
- Observed weather value when available.
- Unit.
- Resolution source.
- Resolution timestamp.
- Raw source payload.

Outcomes should be source-attributed. If the source is uncertain or manually seeded, the record should say so.

## Replay Rules

The replay runner should:

- Select a fixed model version.
- Select an evaluation window.
- Use only snapshots available at prediction time.
- Link each evaluated prediction to one outcome.
- Skip or report records with missing required inputs.
- Produce deterministic output for seed fixtures.

Current outcome-selection rule:

- Within the requested evaluation window, the runner selects one resolved outcome per market.
- If multiple resolved outcomes exist for the same market, the latest `resolved_at` record wins, with the highest record ID used as a deterministic tie-breaker.
- Metrics, EV recommendation counts, and paper-trade settlement summaries use that selected outcome instead of multiplying predictions by every outcome row.

Current initial implementation:

- `POST /backtests/resolved-outcomes` stores manually supplied YES/NO resolved outcomes.
- `GET /backtests/resolved-outcomes` lists stored outcomes, optionally filtered by market.
- `POST /backtests/resolved-outcomes/resolve-weather` resolves a parsed precipitation market from observed daily precipitation and stores a source-attributed outcome.
- Open-Meteo archive remains the default observed-weather provider.
- The observed-weather resolver can normalize NOAA/NCEI CDO-style daily `PRCP` records with explicit precipitation units.
- `resolution_provider: "noaa_cdo_daily"` uses the credential-gated NOAA/NCEI CDO client when `NOAA_CDO_TOKEN` is configured. Missing credentials fail before any provider request.
- `POST /backtests/run` replays persisted predictions against the selected resolved outcome for each market for a model version and date window.
- `seed_fixtures: true` inserts and replays a deterministic small fixture history.
- The initial report includes prediction count, resolved outcome count, win rate, Brier score, log loss, calibration buckets, a sample-size note, EV recommendation count, paper-trade count, paper PnL, paper ROI, and max drawdown.
- Backtest responses include `coverage_diagnostics` so skipped or unevaluated records are visible. The diagnostics report candidate predictions for the selected model, evaluated prediction/outcome pairs, predictions missing outcomes in the requested window, resolved outcomes without matching selected-model predictions, and predictions excluded because they belong to another model version. `resolved_outcome_count_in_window` still reports raw outcome records, so duplicate or corrected outcome rows remain visible even though replay selects one outcome per market.

## Metrics

Backtest reports should include:

- Model version.
- Evaluation window.
- Prediction count.
- Win rate. Implemented for prediction direction.
- Brier score. Implemented.
- Log loss. Implemented.
- Calibration buckets. Implemented.
- Paper-trade count. Implemented for trades linked to recommendations from the selected model version.
- Paper ROI. Implemented as settlement PnL divided by entry cost.
- Max drawdown when enough trade history exists. Implemented over ordered settlement PnL.
- Coverage diagnostics. Implemented for missing outcomes, unmatched outcomes, and model-version exclusions.

## Calibration Buckets

Recommended buckets:

- 0.00 to 0.20
- 0.20 to 0.40
- 0.40 to 0.60
- 0.60 to 0.80
- 0.80 to 1.00

Each bucket should report:

- Number of predictions.
- Average predicted probability.
- Observed YES rate.
- Calibration gap.

Small sample sizes should be called out directly.

## Evidence Threshold Before Live Trading

Live trading should not be enabled only because the API workflow works.

Before live execution is considered, the project should have:

- A working paper-trading workflow.
- Backtest or replay output with real metrics.
- Calibration reporting.
- Documented sample-size limits.
- A safety foundation for live mode.

The threshold is not a fixed profit number. The goal is to show that the strategy has enough measured behavior to justify risk controls and further investigation.

## Tests

Backtesting tests should cover:

- Brier score calculation. Initial coverage exists through replay tests.
- Log loss calculation. Initial coverage exists through replay tests.
- Calibration bucket assignment. Implemented.
- Replay with a small deterministic fixture. Implemented.
- Paper-trade settlement summary. Implemented.
- Handling missing outcomes. Implemented through coverage diagnostics tests.
- Handling mismatched model versions. Implemented through coverage diagnostics tests.
- Observed-weather outcome resolution from fixture or mocked provider payloads. Initial Open-Meteo archive precipitation coverage is implemented, and NOAA/NCEI CDO-style daily `PRCP` normalization is covered for valid, missing-unit, mixed-unit, missing-token, mocked-success, and provider-failure cases.

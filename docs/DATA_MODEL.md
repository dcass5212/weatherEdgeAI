# Data Model

## Purpose

WeatherEdge AI uses a relational data model to preserve the full research workflow from source market discovery through paper-trade evaluation. The model is designed around snapshots and provenance so predictions can be reproduced and later evaluated.

## Core Entity Flow

```text
Market
  -> ParsedMarket
    -> WeatherForecastSnapshot
      -> Prediction
        -> EVRecommendation
          -> PaperTrade

Market
  -> MarketPriceSnapshot
  -> ResolvedOutcome
  -> PaperRunnerRun
```

## `markets`

Stores source market metadata.

Important fields:

- `source`: market data source, such as mock or a Polymarket-style source.
- `source_market_id`: unique ID from the source.
- `condition_id`: optional source condition identifier.
- `question`: market question text.
- `slug`: source slug.
- `category`: source category.
- `active`: whether the market is active.
- `closed`: whether the market is closed.
- `end_time`: market end time when available.
- `resolution_source`: source-provided resolution rules or reference.
- `raw_json`: original source payload.
- `source_diagnostics`: source capability and unsupported-field diagnostics captured during discovery or price refresh.

Important constraint:

- Unique by `source` and `source_market_id`.

Relationships:

- One market has many parsed markets.
- One market has many price snapshots.
- One market has many predictions.
- One market has many resolved outcomes.
- One market has many paper trades.

## `parsed_markets`

Stores structured weather targets extracted from market questions.

Important fields:

- `market_id`: source market.
- `location_name`: parsed location.
- `latitude` and `longitude`: coordinates used for forecast requests.
- `metric`: currently precipitation.
- `operator`: one-sided precipitation threshold comparison, currently `>`, `>=`, `<`, or `<=`.
- `threshold_value`: numeric threshold.
- `threshold_unit`: currently inches or millimeters for V1 one-sided precipitation thresholds.
- `target_start` and `target_end`: target weather window.
- `parse_confidence`: parser confidence estimate.
- `parser_version`: parser version string.
- `raw_parse_json`: full parser output.

Important constraint:

- `threshold_value > 0`.

Design note:

- Multiple parsed records can exist for the same market as the parser and geocoding improve. Predictions should link to the parsed market record they used.
- The parser extracts location text; the parse route resolves coordinates through a deterministic geocoder before persisting the parsed market.

## `market_price_snapshots`

Stores market prices at a point in time.

Important fields:

- `market_id`: source market.
- `yes_price` and `no_price`: market-implied prices.
- `best_bid_yes`, `best_ask_yes`, `best_bid_no`, `best_ask_no`: optional book fields.
- `spread`: bid/ask spread or derived spread.
- `liquidity`: available liquidity.
- `volume`: traded volume.
- `timestamp`: price observation time.
- `raw_json`: original price payload.

Design note:

- Price snapshots should not be overwritten. Strategy evaluation should link to the specific snapshot it used.
- Market discovery is the primary source of price snapshots. Mock discovery stores deterministic demo prices, and public-source discovery stores normalized source prices when fields are available.
- `POST /markets/{market_id}/price-snapshots/refresh` creates a new snapshot from a fresh public source payload for Polymarket-sourced markets, and from the stored raw source payload for manually seeded or non-public markets.
- Refresh attempts update the parent market's `source_diagnostics` so unsupported or partial price payloads are inspectable even when no new snapshot can be created.
- Market parsing does not create demo price snapshots. Price records should come from discovery or an explicit refresh path so strategy decisions retain source provenance.

## `weather_forecast_snapshots`

Stores forecast data used by models.

Important fields:

- `parsed_market_id`: parsed target the forecast belongs to.
- `forecast_source`: weather provider, initially Open-Meteo.
- `forecast_timestamp`: forecast issue or retrieval timestamp.
- `target_start` and `target_end`: forecast target window.
- `forecast_precip_total`: normalized precipitation total.
- `forecast_precip_unit`: unit for precipitation.
- `forecast_temp_max` and `forecast_temp_min`: optional temperature fields.
- `forecast_temp_unit`: temperature unit.
- `raw_json`: original forecast payload.

Design note:

- Forecast snapshots are critical for reproducibility. A prediction should always identify the exact forecast snapshot used.
- Forecast normalization preserves the raw provider payload while storing normalized precipitation and temperature summary fields for modeling.

## `predictions`

Stores model outputs.

Important fields:

- `market_id`: source market.
- `parsed_market_id`: parsed target used by the model.
- `forecast_snapshot_id`: forecast snapshot used by the model.
- `model_version`: model identifier, such as `baseline_precip_v1`.
- `p_yes`: estimated probability of YES.
- `p_no`: estimated probability of NO.
- `confidence`: coarse confidence label.
- `features_json`: feature payload used by the model.

Important constraints:

- `p_yes` must be between 0 and 1.
- `p_no` must be between 0 and 1.

Design note:

- Predictions are immutable research records. Do not update old predictions when a new model version exists; create new prediction records.
- Prediction API responses expose the parsed market and forecast snapshot IDs so reviewers can trace which structured weather target and forecast input produced a probability.

## `ev_recommendations`

Stores expected-value analysis based on a prediction and a price snapshot.

Important fields:

- `prediction_id`: model prediction used.
- `price_snapshot_id`: market price snapshot used.
- `market_price_yes` and `market_price_no`: prices used in the calculation.
- `edge_yes` and `edge_no`: probability edge versus market price.
- `ev_yes` and `ev_no`: expected-value estimates.
- `recommendation`: `AVOID`, `WATCH`, `PAPER_BUY_YES`, or `PAPER_BUY_NO`.
- `paper_position_size`: simulated size suggestion.
- `reason`: human-readable explanation.

Design note:

- Recommendations should feed paper trading first. Later live execution should create separate execution/order records from approved recommendations rather than mutating the recommendation itself.
- Strategy evaluation responses expose `prediction_id`, `price_snapshot_id`, and the prediction's parsed-market and forecast-snapshot IDs so expected-value decisions are reproducible from stored inputs.
- Current paper sizing converts positive edge into simulated units by multiplying by 100 and capping at 10 units. This is a paper-mode research rule, not a live-trading risk limit.

## `paper_trades`

Stores simulated positions created from EV recommendations.

Important fields:

- `market_id`: source market.
- `recommendation_id`: EV recommendation behind the trade.
- `side`: simulated YES or NO side.
- `entry_price`: simulated entry price.
- `quantity`: simulated quantity.
- `entry_time`: simulated entry time.
- `exit_price`: simulated exit price.
- `exit_time`: simulated exit time.
- `pnl`: simulated profit/loss.
- `status`: `OPEN` or closed-like state.

Important constraints:

- `quantity > 0`.
- `entry_price` must be between 0 and 1.

Design note:

- Paper trades are portfolio demo records and research signals. They do not represent real positions.

## `resolved_outcomes`

Stores final market/weather outcomes for evaluation.

Important fields:

- `market_id`: source market.
- `actual_outcome`: resolved YES/NO-like outcome.
- `actual_value`: observed weather value.
- `actual_unit`: observed unit.
- `resolution_source`: source used for outcome verification.
- `resolved_at`: resolution time.
- `raw_json`: original resolution payload.

Design note:

- Resolved outcomes are required for real backtesting and calibration.
- Backtest replay selects one resolved outcome per market inside the requested evaluation window. If multiple outcome records exist for a market, the latest `resolved_at` record is used, with highest record ID as a deterministic tie-breaker. Raw outcome counts remain visible in coverage diagnostics.

## `paper_runner_runs`

Stores one auditable record per public-market paper runner pass.

Important fields:

- `status`: `running`, `completed`, or `failed`.
- `source`: market source used by the run.
- `started_at` and `completed_at`: run timing.
- `config_json`: discovery, processing, eligibility, dry-run, and trade-cap settings used.
- Summary counts for discovered, processed, parsed, forecast, prediction, recommendation, and simulated trade creation.
- `skipped_json`: skip reasons and counts.
- `errors_json`: workflow errors captured during the run.
- `report_json`: compact report payload returned by the runner.

Design note:

- These records make automated paper trading inspectable without implying live execution. They are operational run logs, not positions or orders.
- `GET /paper-runner/diagnostics` aggregates these run records with market `source_diagnostics` so reviewers can inspect skipped-market reasons, unsupported public price payloads, stale-price fallback, and recent workflow errors without rerunning public data collection.

## Lifecycle Of A Market

1. Market is discovered and stored in `markets`.
2. Market prices are stored in `market_price_snapshots`.
3. Market question is parsed into `parsed_markets`.
4. Forecast is fetched and stored in `weather_forecast_snapshots`.
5. Model creates a `predictions` record.
6. Strategy creates an `ev_recommendations` record.
7. Optional simulated trade creates a `paper_trades` record.
8. Automated public paper passes also create `paper_runner_runs` records for auditability.
9. Later, final outcome is stored in `resolved_outcomes`.
10. Backtesting compares predictions and paper trades against outcomes.

## API Workflow Status

`GET /markets/{market_id}` includes a computed `workflow_status` object. This is not a stored table; it is derived from the latest related records so the API can show which workflow steps have already run.

Fields:

- `has_price_snapshot`
- `has_parsed_market`
- `has_forecast_snapshot`
- `has_prediction`
- `has_ev_recommendation`
- `has_paper_trade`
- `next_action`

`next_action` is a compact hint for the next backend call: refresh prices, parse the market, create a forecast, run prediction, evaluate strategy, proceed to paper-trade creation, or monitor an existing paper trade.

The same response includes the latest parsed market, price snapshot, forecast snapshot, prediction, EV recommendation, and paper trade when those records exist. These are read-time joins for demo and dashboard inspection, not separate aggregate tables.

## Migration Plan

Alembic manages the PostgreSQL schema from the current ORM models. The initial migration creates the core workflow tables for markets, parsed targets, market price snapshots, forecast snapshots, predictions, EV recommendations, paper trades, and resolved outcomes. A later migration adds market-level `source_diagnostics` for public data integration debugging.

Schema changes after that should:

- Be migration-backed.
- Preserve existing data where practical.
- Add indexes for common query paths.
- Keep historical snapshots intact.

Local migration commands:

```powershell
cd C:\weatherEdgeAI\backend
alembic upgrade head
```

```powershell
cd C:\weatherEdgeAI\backend
alembic revision --autogenerate -m "describe schema change"
```

## Live-Trading Data Model Progression

The current data model supports research, paper trading, and evaluation. Live-trading execution state should be added only after the paper-trading and backtesting workflow is credible.

Live-trading-specific concepts that may be added later behind explicit safety controls:

- Real orders.
- Exchange credentials.
- Wallet accounts.
- Signed transactions.
- Live positions.
- Execution logs.
- Kill-switch state.

Paper-trading records and live execution records must remain separate. Paper mode must stay the default, and tests must prove paper-mode workflows cannot place real orders. Current configuration defaults to `TRADING_MODE=paper` and `LIVE_TRADING_ENABLED=false`; live execution records do not exist yet.

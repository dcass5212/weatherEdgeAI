# API Workflows

## Purpose

This document describes the intended end-to-end API workflows for WeatherEdge AI. It is more important than a raw endpoint list because the portfolio value comes from the pipeline: market discovery to parsing to forecast to prediction to expected-value analysis to paper trading, with a later safety-gated path to live execution.

Base local URL:

```text
http://127.0.0.1:8000
```

## Health Check

Request:

```http
GET /health
```

Expected result:

```json
{
  "status": "ok",
  "service": "WeatherEdge AI"
}
```

## Workflow 1: Discover Markets

Use market discovery to pull active weather-related markets into the database.

Request:

```http
POST /markets/discover
Content-Type: application/json

{
  "source": "mock",
  "keywords": ["rain", "precipitation"],
  "limit": 10
}
```

Current behavior:

- `source: "mock"` returns deterministic demo markets.
- Non-mock discovery uses a Polymarket-style public market source. It searches Gamma `public-search` by keyword first, deduplicates event results, falls back to active event listing when search returns no candidates, and skips inactive or closed child markets.
- Default non-mock discovery keywords are precipitation-first (`rain`, `rainfall`, `precipitation`, `snow`, `temperature`, `inch`, `mm`) so automated collection does not start from the broad `weather` query that currently returns many space-weather event-count markets.
- Discovered markets are persisted idempotently by source and source market ID.
- Discovery persists source-aware market price snapshots when source price data is available.
- Discovery stores market-level `source_diagnostics` describing supported metadata, price, top-of-book, Gamma/CLOB liquidity and volume fields, status, and resolution fields.

Expected response shape:

```json
{
  "discovered": 2,
  "created": 2,
  "updated": 0,
  "price_snapshots_created": 2
}
```

Next endpoint:

```http
GET /markets
```

Use the returned market IDs for the rest of the workflow.

Read a market's current pipeline state:

```http
GET /markets/{market_id}
```

The detail response includes `workflow_status` so clients and reviewers can see what has been completed and what should happen next:

```json
{
  "workflow_status": {
    "has_price_snapshot": true,
    "has_parsed_market": true,
    "has_forecast_snapshot": false,
    "has_prediction": false,
    "has_ev_recommendation": false,
    "has_paper_trade": false,
    "next_action": "create_forecast"
  }
}
```

The detail response also includes the latest parsed market, price snapshot, forecast snapshot, prediction, EV recommendation, and paper trade when those records exist. This makes `GET /markets/{market_id}` the compact inspection endpoint for the full paper-trading workflow.

Current `next_action` values:

- `refresh_price_snapshot`
- `parse_market`
- `create_forecast`
- `run_prediction`
- `evaluate_strategy`
- `ready_for_paper_trade`
- `monitor_paper_trade`

## Workflow 1A: Refresh A Market Price Snapshot

Refresh a market price snapshot from the source. Polymarket markets use a fresh public payload; manually seeded or non-public markets use their stored payload.

Request:

```http
POST /markets/{market_id}/price-snapshots/refresh
```

Current behavior:

- Polymarket-sourced markets fetch a fresh Gamma market payload before normalization and may enrich it with public CLOB market information when condition-id metadata is available.
- Optional CLOB condition-id lookup failures do not block refresh when the fresh Gamma payload is available.
- Public source requests retry transient failures and rate limits within a small retry budget.
- Fresh Polymarket price payloads are combined with stored market context when token-only price maps need the market's outcome and token-id metadata.
- Non-public or manually seeded markets continue to use the stored raw source payload when present.
- The public paper runner requires fresh prices by default. It can continue from the latest stored discovery-time price snapshot only when `allow_stale_price_fallback: true` is passed on the API or `--allow-stale-price-fallback` is set on the CLI. In that opt-in path the market keeps `source_refresh_failed` diagnostics with `price_status: "stale_supported"` and a `fallback_price_snapshot_id`.
- Normalizes common Polymarket-style fields such as YES/NO outcome prices, token outcome prices, midpoint or last trade price, CLOB orderbook bid/ask levels, CLOB token BUY/SELL price maps, spread, liquidity, and volume.
- Handles common wrapped public payloads where the market object is nested under `market` or `data`, plus token rows that expose `lastPrice` or `last_price`.
- Persists a new immutable `market_price_snapshots` record.
- Updates the market's `source_diagnostics` for supported, partial, and unsupported payloads.
- Records specific partial-price diagnostics for recognizable unsupported shapes, including `non_binary_outcomes`, `outcome_price_length_mismatch`, `missing_token_context`, and `empty_orderbook`.
- Does not place orders, sign transactions, access credentials, or use authenticated trading APIs.

Expected response fields:

```json
{
  "id": 1,
  "market_id": 1,
  "yes_price": 0.57,
  "no_price": 0.43,
  "best_bid_yes": 0.56,
  "best_ask_yes": 0.58,
  "spread": 0.02,
  "liquidity": 900.0,
  "volume": 1200.0
}
```

Failure cases:

- `404` when the market does not exist.
- `409` when the market has no stored source payload.
- `409` when the source payload does not include supported price fields. In that case the market record keeps diagnostics such as `price_status: "unsupported"` and unsupported reasons.
- `502` when a public market-data source request fails. The market keeps source diagnostics with `source_refresh_failed` plus `public_source_error` fields for endpoint, reason, retry attempts, status code, and whether the failure was retryable.

## Workflow 1B: Read Dashboard Summary

Use the dashboard summary endpoint as the first frontend contract. It is read-only and aggregates the latest inspection records without creating trades, refreshing prices, or calling external providers.

Request:

```http
GET /dashboard/summary
```

## Workflow 1C: Run Paper Demo Workflow

Use this endpoint from the dashboard when you want one paper-only action to seed and advance the deterministic demo workflow.

Request:

```http
POST /demo/paper-workflow
Content-Type: application/json

{
  "quantity": 10
}
```

Current behavior:

- Uses mock market discovery only.
- Selects the deterministic New York City rain market.
- Parses the market with the rule-based precipitation parser.
- Uses the fixture geocoder and a deterministic `demo_fixture` forecast.
- Runs the baseline precipitation model.
- Evaluates EV against the mock discovery price snapshot.
- Creates an open paper trade only when the recommendation is `PAPER_BUY_YES` or `PAPER_BUY_NO`.
- Reuses existing parsed market, forecast, prediction, recommendation, and paper trade records on repeated clicks.
- Does not call external market/weather providers, place orders, sign transactions, access credentials, or use live execution adapters.

Expected response shape:

```json
{
  "market_id": 1,
  "parsed_market_id": 1,
  "forecast_snapshot_id": 1,
  "prediction_id": 1,
  "recommendation_id": 1,
  "paper_trade_id": 1,
  "recommendation": "PAPER_BUY_YES",
  "steps_completed": ["mock_discovery", "parsed_market", "fixture_forecast", "prediction", "ev_recommendation", "paper_trade"],
  "message": "Paper demo workflow complete."
}
```

Optional query parameters:

- `market_limit`: recent market summaries to return, default `10`, max `50`.
- `opportunity_limit`: recent actionable paper opportunities to return, default `10`, max `50`.
- `trade_limit`: open paper trades to return, default `10`, max `50`.
- `model_version`: model version for the compact evaluation summary, default `baseline_precip_v1`.

Current behavior:

- Returns recent markets with workflow status and latest record IDs for price snapshot, parsed market, forecast snapshot, prediction, EV recommendation, and paper trade.
- Includes compact latest inspection values for the parsed weather target, forecast precipitation total, model YES probability, market YES price, YES edge, EV recommendation, and paper-trade status.
- Includes compact source diagnostics for each recent market: `source`, `price_status`, `unsupported_reasons`, and whether a public source error was recorded.
- Labels recoverable stale-price fallback as `using stored price` when a public refresh fails but a stored binary snapshot remains usable.
- Returns recent paper-buy opportunities.
- Returns open paper trades.
- Returns recent public paper-runner history, including run status, dry-run flag, workflow counts, skip reasons, and errors.
- Returns a compact backtest and calibration summary. The endpoint first tries a read-only persisted replay over existing resolved outcomes for the requested model version. If no completed persisted replay exists, it returns deterministic seed-fixture metrics without writing seed records.
- Does not place orders, create paper trades, refresh public data, or call weather providers.

Expected response shape:

```json
{
  "recent_markets": [
    {
      "market_id": 1,
      "question": "Will New York City get more than 1 inch of rain tomorrow?",
      "source": "mock",
      "price_status": "supported",
      "unsupported_reasons": [],
      "has_public_source_error": false,
      "source_error_label": null,
      "latest_price_snapshot_id": 1,
      "latest_parsed_market_id": 1,
      "latest_forecast_snapshot_id": 1,
      "latest_prediction_id": 1,
      "latest_ev_recommendation_id": 1,
      "latest_paper_trade_id": 1,
      "parsed_target": "New York City precipitation > 1 inch",
      "forecast_precip_total": 1.6,
      "forecast_precip_unit": "inch",
      "model_probability_yes": 0.75,
      "market_price_yes": 0.44,
      "edge_yes": 0.31,
      "recommendation": "PAPER_BUY_YES",
      "paper_trade_status": "OPEN",
      "workflow_status": {
        "has_price_snapshot": true,
        "has_parsed_market": true,
        "has_forecast_snapshot": true,
        "has_prediction": true,
        "has_ev_recommendation": true,
        "has_paper_trade": true,
        "next_action": "monitor_paper_trade"
      }
    }
  ],
  "opportunities": [],
  "open_paper_trades": [],
  "recent_paper_runs": [
    {
      "id": 1,
      "status": "completed",
      "source": "polymarket",
      "started_at": "2026-05-09T12:00:00Z",
      "completed_at": "2026-05-09T12:01:00Z",
      "dry_run": true,
      "discovered": 25,
      "processed": 10,
      "parsed": 3,
      "forecasts_created": 2,
      "predictions_created": 2,
      "recommendations_created": 2,
      "paper_trades_created": 0,
      "skipped": {
        "missing_coordinates": 4
      },
      "errors": []
    }
  ],
  "evaluation_summary": {
    "model_version": "baseline_precip_v1",
    "source": "seed_fixture",
    "status": "completed",
    "num_predictions": 3,
    "num_resolved_outcomes": 3,
    "win_rate": 0.666667,
    "brier_score": 0.194167,
    "log_loss": 0.5716,
    "paper_gross_pnl": 5.8,
    "paper_fee_cost": 0.0,
    "paper_slippage_cost": 0.0,
    "paper_roi": 0.408451,
    "paper_total_pnl": 5.8,
    "max_drawdown": 4.5,
    "paper_settlement_note": "Paper settlement applies 0.0000 fee rate and 0.0000 entry slippage rate; paper_total_pnl and paper_roi are net of those assumptions.",
    "sample_size_note": "Very small sample; use metrics only to verify the replay workflow.",
    "calibration_buckets": []
  }
}
```

### Frontend Usage

The `frontend/` app is the first dashboard implementation for this contract. It is intentionally read-only and uses the Vite dev-server proxy at `/api` to call the FastAPI backend locally.

Current frontend behavior:

- Reads `GET /health`.
- Reads `GET /dashboard/summary`.
- Reads `GET /paper-trades` and `GET /paper-trades?status=OPEN` for open and historical paper-trade views.
- Reads `GET /backtests/resolved-outcomes` for the outcome log.
- Shows recent market workflow rows with compact latest parsed target, forecast, model, price, EV, and paper-trade status values.
- Shows compact market source diagnostics, including supported/partial/unsupported price status and unsupported reasons.
- Shows compact backtest metrics, paper replay metrics, calibration buckets, and sample-size context.
- Shows paper-buy opportunities, open paper trades, all stored paper trades, and resolved outcome logs.
- Shows recent public paper-runner runs with status, dry-run mode, workflow counts, skip reasons, and errors.
- Provides a `Run Paper Demo` button that calls only `POST /demo/paper-workflow`.
- Provides a run console for `POST /paper-runner/run-once` with dry-run, max-trade, quantity, liquidity, and spread controls. Dry-run remains the default public setting; turning it off creates simulated paper trades only.
- Does not expose live-trading controls.

Run it after starting the backend:

```powershell
cd C:\weatherEdgeAI\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Workflow 2: Parse A Market

Parse a market question into a structured weather target.

Request:

```http
POST /markets/{market_id}/parse
```

Optional query parameter:

- `allow_interval_contracts`: defaults to `false`; set to `true` to parse `between X-Y` precipitation interval contracts.

Current behavior:

- Parses precipitation threshold questions.
- Extracts location, metric, operator, threshold, unit, and target window when possible.
- Supports common V1 precipitation wording such as `more than 1 inch of rain`, `over 1 inch of precipitation`, `at least 0.5 inches of rain`, `0.5 inches or more of rain`, `less than 2 inches of precipitation`, `240mm or more of precipitation`, and `more than 1 inch of rain in New York City`.
- Interval contracts such as `between 190-200mm of precipitation` are supported only when `allow_interval_contracts=true` is passed to the parse endpoint or the paper-runner interval toggle is enabled. They use a simple interval baseline and should be treated as experimental research signals.
- Parsed locations are resolved through a deterministic fixture geocoder for New York City, NYC, New York, Chicago, London, and Hong Kong by default.
- A broader Open-Meteo geocoding provider is available behind the same adapter when `GEOCODING_PROVIDER=open_meteo`.
- Parsing does not create market price snapshots. Use market discovery or `POST /markets/{market_id}/price-snapshots/refresh` so strategy evaluation can trace prices to a source payload.

Expected response fields:

```json
{
  "id": 1,
  "market_id": 1,
  "location_name": "New York City",
  "latitude": 40.7128,
  "longitude": -74.006,
  "metric": "precipitation",
  "operator": ">",
  "threshold_value": 1.0,
  "threshold_unit": "inch",
  "parse_confidence": 0.8,
  "parser_version": "..."
}
```

Failure cases:

- `404` when the market does not exist.
- `422` when the question cannot be parsed into a supported precipitation market. Parser failures now distinguish non-precipitation questions, missing numeric thresholds, unsupported units, interval contracts that need opt-in interval probability modeling, and other unsupported precipitation wording.
- Parsed markets with unsupported locations can still be stored, but forecast creation will fail until coordinates are available.
- `502` when an enabled external geocoding provider request fails.

## Workflow 3: Fetch Forecast Snapshot

Fetch and persist a weather forecast for the parsed market.

Request:

```http
POST /weather/forecast/{parsed_market_id}
```

Current behavior:

- Requires the parsed market to have latitude and longitude.
- Calls Open-Meteo through the weather service.
- Persists a `weather_forecast_snapshots` record.
- Normalizes daily precipitation totals defensively from Open-Meteo payloads, including numeric strings, missing values, malformed lists, millimeter-to-inch conversion, temperature min/max, and raw payload preservation.

Expected response fields:

```json
{
  "id": 1,
  "parsed_market_id": 1,
  "forecast_source": "open_meteo",
  "forecast_timestamp": "2026-05-05T00:00:00Z",
  "forecast_precip_total": 0.7,
  "forecast_precip_unit": "inch"
}
```

Read latest forecast:

```http
GET /weather/forecast/{parsed_market_id}/latest
```

Failure cases:

- `404` when the parsed market does not exist.
- `422` when coordinates or required target data are missing.
- `502` when the external weather request fails.

## Workflow 4: Run Prediction

Run a versioned probability model for a market.

Request:

```http
POST /predictions/run/{market_id}
```

Optional query parameter:

- `model_version`: defaults to `baseline_precip_v1`; supported values are currently `baseline_precip_v1` and `logistic_precip_v1`.

Current behavior:

- Uses the latest parsed market.
- Uses the latest forecast snapshot for that parsed market.
- Stores a prediction with model version, probabilities, confidence, and feature payload.
- The stored prediction records the exact `parsed_market_id` and `forecast_snapshot_id` used for reproducibility.
- `baseline_precip_v1` remains the default transparent banded baseline.
- `logistic_precip_v1` uses a fixed-coefficient logistic regression formula over forecast-vs-threshold features. Its coefficients are hand-selected initial coefficients, not trained performance evidence.

Expected response fields:

```json
{
  "id": 1,
  "market_id": 1,
  "parsed_market_id": 1,
  "forecast_snapshot_id": 1,
  "model_version": "baseline_precip_v1",
  "p_yes": 0.6,
  "p_no": 0.4,
  "confidence": "medium"
}
```

Read predictions:

```http
GET /predictions/{market_id}
GET /predictions/{market_id}/latest
```

Failure cases:

- `404` when the market does not exist.
- `409` when parsing or forecast snapshot creation has not happened yet.
- `422` when an unsupported `model_version` is requested.

## Workflow 5: Evaluate Strategy

Compare the latest model prediction with the latest market price snapshot.

Request:

```http
POST /strategy/evaluate/{market_id}
```

Current behavior:

- Requires a latest prediction.
- Requires a latest market price snapshot.
- Computes YES/NO edge and expected value.
- Stores an `ev_recommendations` record.
- The stored recommendation records the exact `prediction_id` and `price_snapshot_id` used.
- The response also includes the prediction's `parsed_market_id` and `forecast_snapshot_id` so the full input chain is visible in one API call.
- Produces one of `AVOID`, `WATCH`, `PAPER_BUY_YES`, or `PAPER_BUY_NO`.
- For paper-buy recommendations, `paper_position_size` uses a simple paper-mode sizing rule: positive edge is converted to percentage points and capped at 10 simulated units. For example, a 3.5 percentage-point edge suggests 3.5 units; a 31 percentage-point edge is capped at 10 units. Non-actionable recommendations leave size empty.

Expected response fields:

```json
{
  "market_id": 1,
  "prediction_id": 1,
  "parsed_market_id": 1,
  "forecast_snapshot_id": 1,
  "price_snapshot_id": 1,
  "model_probability_yes": 0.6,
  "market_price_yes": 0.44,
  "edge_yes": 0.16,
  "recommendation": "PAPER_BUY_YES",
  "paper_position_size": 10.0,
  "reason": "Model probability exceeds market-implied probability by 16%; paper size is 10.00 with a 10.00 max."
}
```

List recent opportunities:

```http
GET /strategy/opportunities?min_edge=0.03&limit=20
```

Opportunity rows include `prediction_id` and `price_snapshot_id` so a reviewer can inspect the stored inputs behind each paper-trading signal.

## Workflow 6: Create And Close Paper Trades

Create a simulated trade from an EV recommendation.

Request:

```http
POST /paper-trades
Content-Type: application/json

{
  "recommendation_id": 1,
  "quantity": 10
}
```

Current behavior:

- Creates a paper trade only from an existing EV recommendation.
- Does not place real orders.
- Remains the default execution mode for local development, tests, demos, and strategy validation.
- Stores a compact `signal_snapshot_json` on the paper trade so the entry can be explained later from the exact parsed target, forecast, prediction, market price, edge, liquidity, spread, recommendation reason, and runner config available at creation time.

List paper trades:

```http
GET /paper-trades
GET /paper-trades?status=OPEN
```

Close a paper trade:

```http
POST /paper-trades/{paper_trade_id}/close
Content-Type: application/json

{
  "exit_price": 0.73
}
```

Paper trade reads include `signal_snapshot_json` when available.

## Workflow 7: Backtest

Run a replay over stored predictions that have resolved outcomes. For a deterministic local demo, set `seed_fixtures` to `true` to insert and replay a small fixture-backed history.

```http
POST /backtests/run
Content-Type: application/json

{
  "start_date": "2026-05-01",
  "end_date": "2026-05-10",
  "model_version": "baseline_precip_v1",
  "seed_fixtures": true,
  "paper_fee_rate": 0.0,
  "paper_slippage_rate": 0.0
}
```

Run a walk-forward replay when you want the same persisted-record evaluation
split into rolling date windows:

```http
POST /backtests/walk-forward
Content-Type: application/json

{
  "start_date": "2026-05-01",
  "end_date": "2026-05-31",
  "model_version": "baseline_precip_v1",
  "window_days": 7,
  "step_days": 1,
  "paper_fee_rate": 0.0,
  "paper_slippage_rate": 0.0
}
```

Current walk-forward behavior:

- Uses persisted records only.
- Runs the normal backtest replay for each inclusive rolling window.
- Returns each window's full backtest response.
- Aggregates evaluated prediction counts, resolved outcome counts, EV recommendation counts, paper-trade counts, paper PnL totals, weighted average Brier score, weighted average log loss, and weighted average win rate.
- Adds interpretation limits when windows overlap, outcomes are sparse, or some windows have no resolved predictions.

If `step_days` is smaller than `window_days`, some evaluated records can appear
in more than one window. Treat aggregate counts as rolling-window counts rather
than unique prediction counts.

Current behavior:

- Replays stored predictions joined to `resolved_outcomes` by market.
- Selects one latest resolved outcome per market in the requested evaluation window before calculating metrics, so corrected or duplicate outcome rows do not multiply predictions.
- Filters by model version and resolved-at date window.
- Reports prediction count, resolved outcome count, win rate, Brier score, log loss, calibration buckets, and a sample-size note.
- Reports a `sample_size_gate` of `insufficient_sample`, `early_signal`, or `reviewable_sample`.
- Reports baseline comparisons for the model probability, an always-50% control, and market-implied probability when linked market YES prices exist.
- Reports EV recommendation count, eligible paper-trade count, gross paper PnL, fee and slippage costs, net settlement PnL, paper ROI, and max drawdown for trades linked to recommendations from the selected model version.
- Paper-trade settlement uses request-level `paper_fee_rate` and `paper_slippage_rate` assumptions. Both default to `0.0`; when set, `paper_total_pnl` and `paper_roi` are net of those costs while `paper_gross_pnl`, `paper_fee_cost`, and `paper_slippage_cost` keep the assumptions inspectable.
- Reports coverage diagnostics for candidate predictions, evaluated prediction/outcome pairs, missing outcomes, unmatched outcomes, and predictions excluded by model version.

Create a resolved outcome:

```http
POST /backtests/resolved-outcomes
Content-Type: application/json

{
  "market_id": 1,
  "actual_outcome": "YES",
  "actual_value": 1.24,
  "actual_unit": "inch",
  "resolution_source": "manual_review",
  "resolved_at": "2026-05-06T02:00:00Z",
  "raw_json": {
    "note": "Seeded example"
  }
}
```

List resolved outcomes:

```http
GET /backtests/resolved-outcomes
GET /backtests/resolved-outcomes?market_id=1
```

Resolve a parsed precipitation market from observed weather data:

```http
POST /backtests/resolved-outcomes/resolve-weather
Content-Type: application/json

{
  "market_id": 1,
  "resolution_provider": "open_meteo_archive"
}
```

Current behavior:

- Uses the market's latest parsed weather target.
- Requires parsed latitude, longitude, and target dates.
- Defaults to Open-Meteo archive when `resolution_provider` is omitted.
- Supports `resolution_provider: "open_meteo_archive"` for public archive observations.
- Supports `resolution_provider: "noaa_cdo_daily"` for credential-gated NOAA/NCEI CDO daily `PRCP` observations when `NOAA_CDO_TOKEN` is configured.
- Converts millimeters to inches when needed and compares the observed total to the parsed threshold.
- Persists a normal `resolved_outcomes` record with the selected `resolution_source` and the raw provider payload.
- Fails closed with `422` when the NOAA provider is requested without credentials.
- Returns `502` when an observed-weather provider request fails.

### Observed Outcome Provider Usage

Use Open-Meteo archive for the normal local workflow. It is the default and does not require credentials:

```http
POST /backtests/resolved-outcomes/resolve-weather
Content-Type: application/json

{
  "market_id": 1
}
```

Use the same endpoint with an explicit Open-Meteo provider when you want the request body to show the selected source:

```http
POST /backtests/resolved-outcomes/resolve-weather
Content-Type: application/json

{
  "market_id": 1,
  "resolution_provider": "open_meteo_archive"
}
```

Use NOAA/NCEI CDO only for manual observed-outcome resolution after configuring a token:

```env
NOAA_CDO_BASE_URL=https://www.ncei.noaa.gov/cdo-web/api/v2
NOAA_CDO_TOKEN=your_token_here
```

```http
POST /backtests/resolved-outcomes/resolve-weather
Content-Type: application/json

{
  "market_id": 1,
  "resolution_provider": "noaa_cdo_daily"
}
```

Provider behavior:

- `open_meteo_archive` requests daily precipitation from Open-Meteo archive by latitude, longitude, and parsed target date window.
- `noaa_cdo_daily` requests NOAA/NCEI CDO daily `PRCP` records using a small coordinate bounding box around the parsed market location.
- Both providers preserve raw payloads under the stored `resolved_outcomes.raw_json` field.
- Both providers compare observed precipitation against the parsed market operator and threshold.
- NOAA requests fail before provider access when `NOAA_CDO_TOKEN` is not configured.

Resolve all eligible completed parsed precipitation markets in one batch:

```http
POST /backtests/resolved-outcomes/resolve-weather-batch
Content-Type: application/json

{
  "resolution_provider": "open_meteo_archive",
  "limit": 100,
  "settle_open_trades": true,
  "skip_existing_outcomes": true
}
```

Current batch behavior:

- Scans parsed markets with coordinates and completed target windows.
- Skips older parsed records for markets already scanned in the batch.
- Skips markets that already have a resolved outcome for the selected provider by default.
- Stores per-market skipped and error results instead of failing the whole batch.
- Settles open simulated paper trades for each newly resolved market by default.

Resolved outcome creation and observed-weather resolution now settle open paper trades for the same market by default. Settlement is paper-only, marks trades `RESOLVED`, and uses a binary side payout: `1.0` for the winning YES/NO side and `0.0` for the losing side.

Preview outcome-resolution eligibility without calling providers or writing records:

```http
GET /backtests/resolved-outcomes/eligibility-preview?resolution_provider=open_meteo_archive&limit=100
```

Current preview behavior:

- Reports parsed markets as `ready`, `not_ready`, `missing_coordinates`, `missing_target_window`, `already_resolved`, or `skipped`.
- Uses the selected provider when deciding whether a market is already resolved.
- Skips older parsed records after the latest record for a market has already been previewed.
- Does not call observed-weather providers, create outcomes, settle trades, or use live execution.

Current NOAA limitation:

- The NOAA client does not yet implement robust station selection. It asks CDO for `PRCP` observations in a small bounding box around the parsed coordinates and normalizes returned daily precipitation records. Future work should add station-choice diagnostics and better handling of multiple nearby stations.

Expected backtest response fields:

```json
{
  "model_version": "baseline_precip_v1",
  "num_predictions": 3,
  "num_resolved_outcomes": 3,
  "coverage_diagnostics": {
    "candidate_prediction_count": 3,
    "evaluated_prediction_count": 3,
    "missing_outcome_count": 0,
    "resolved_outcome_count_in_window": 3,
    "unmatched_resolved_outcome_count": 0,
    "excluded_prediction_model_version_count": 0
  },
  "ev_recommendation_count": 3,
  "paper_trade_count": 3,
  "win_rate": 0.666667,
  "brier_score": 0.194167,
  "log_loss": 0.5716,
  "calibration_buckets": [
    {
      "lower_bound": 0.4,
      "upper_bound": 0.6,
      "count": 1,
      "average_predicted_probability": 0.4,
      "observed_yes_rate": 0.0,
      "calibration_gap": -0.4
    },
    {
      "lower_bound": 0.6,
      "upper_bound": 0.8,
      "count": 2,
      "average_predicted_probability": 0.675,
      "observed_yes_rate": 0.5,
      "calibration_gap": -0.175
    }
  ],
  "sample_size_note": "Very small sample; use metrics only to verify the replay workflow.",
  "sample_size_gate": "insufficient_sample",
  "baseline_comparisons": [
    {
      "name": "model_probability",
      "prediction_count": 3,
      "brier_score": 0.194167,
      "log_loss": 0.5716,
      "win_rate": 0.666667
    }
  ],
  "paper_gross_pnl": 5.8,
  "paper_fee_cost": 0.0,
  "paper_slippage_cost": 0.0,
  "paper_total_pnl": 5.8,
  "paper_roi": 0.408451,
  "max_drawdown": 4.5,
  "paper_settlement_note": "Paper settlement applies 0.0000 fee rate and 0.0000 entry slippage rate; paper_total_pnl and paper_roi are net of those assumptions.",
  "status": "completed",
  "source": "seed_fixture"
}
```

## Workflow 8: Evidence Report

Use the evidence report after a bounded paper run and outcome-resolution batch:

```http
GET /evaluation/evidence-report?start_date=2026-05-01&end_date=2026-05-10&model_version=baseline_precip_v1
```

Current behavior:

- Reads persisted records only.
- Summarizes recent paper-runner counts, skip reasons, and errors.
- Reports prediction, outcome, open trade, resolved trade, and unresolved trade counts.
- Reports paper trade lifecycle counts for recommended buy signals, recommended-but-not-traded signals, open trades, resolved trades, manually closed trades, unresolved trades, and unresolved trades past the target weather window.
- Reports market-implied baseline coverage: evaluated predictions, evaluated predictions with linked market YES prices, missing market-implied comparisons, and coverage ratio.
- Embeds the same backtest metrics returned by `POST /backtests/run`.
- Includes baseline comparisons, sample-size gate, sample-size note, and interpretation limits.
- Does not refresh external data, create trades, or use live execution.

Target behavior:

- Continue broadening observation-provider coverage and source diagnostics as new real payload shapes are captured.

## Main Demo Sequence

Use this sequence for the portfolio demo:

1. `GET /health`
2. `POST /markets/discover`
3. `GET /markets`
4. Optional: `POST /markets/{market_id}/price-snapshots/refresh`
5. `POST /markets/{market_id}/parse`
6. `POST /weather/forecast/{parsed_market_id}`
7. `POST /predictions/run/{market_id}`
8. `POST /strategy/evaluate/{market_id}`
9. `POST /paper-trades`
10. `GET /markets/{market_id}`
11. `GET /strategy/opportunities`
12. `GET /dashboard/summary`

For the browser-first demo, start FastAPI and the frontend, then click `Run Paper Demo` in the dashboard. That button calls `POST /demo/paper-workflow` and refreshes `GET /dashboard/summary`.

## One-Shot Public Paper Runner

For manual public-market paper validation, run the guarded script from the backend directory after PostgreSQL is running and migrations are applied:

```powershell
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --max-trades 3 --quantity 1 --min-liquidity 100 --max-spread 0.15
```

The runner performs one pass:

1. Discovers public weather markets.
2. Persists or updates market records and source price snapshots.
3. Refreshes public prices unless `--no-refresh-prices` is set.
4. Skips ineligible markets using binary-price, liquidity, spread, parse, and coordinate checks.
5. Fetches forecasts, runs predictions, evaluates EV, and creates simulated paper trades within `--max-trades`.

If public price refresh returns an error for a market that already has a usable stored binary price snapshot from discovery, the runner fails closed by default with `price_refresh_failed_fresh_price_required`. When `--allow-stale-price-fallback` or `allow_stale_price_fallback: true` is explicitly enabled, it records `price_refresh_failed_used_stored_snapshot` and continues from that stored snapshot. This keeps public-source instability visible without silently turning a fresh-price run into a stale replay.

Use `--dry-run` to evaluate without creating paper trades. The script is paper-only and does not call authenticated trading APIs, sign transactions, place orders, or create live execution records.

For bounded overnight paper validation, enable loop mode explicitly:

```powershell
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --interval-minutes 30 --max-hours 10 --max-trades 3 --quantity 1 --min-liquidity 100 --max-spread 0.15
```

Loop mode requires `--max-hours` or `--max-runs` so the command does not run indefinitely by accident.

To include interval/range precipitation contracts in a manual pass, enable the experimental toggle:

```powershell
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run --allow-interval-contracts
```

The same behavior can be enabled for API runs with `allow_interval_contracts: true` or as an environment default with `PAPER_RUNNER_ALLOW_INTERVAL_CONTRACTS=true`. Use `--disable-interval-contracts` to opt out in the CLI even when the environment default is enabled.

Each pass persists a `paper_runner_runs` row with the config used, status, start/end timestamps, summary counts, skip reasons, errors, and the compact report payload.

The same one-shot workflow is available through the API:

```http
POST /paper-runner/run-once
Content-Type: application/json

{
  "keywords": ["rain", "precipitation", "snow"],
  "discovery_limit": 25,
  "process_limit": 10,
  "max_trades": 3,
  "quantity": 1,
  "min_liquidity": 100,
  "max_spread": 0.15,
  "refresh_prices": true,
  "dry_run": false,
  "allow_interval_contracts": false,
  "max_price_age_minutes": 120,
  "max_forecast_age_hours": 12,
  "max_open_trades": 5,
  "max_total_exposure": 25,
  "max_market_exposure": 5,
  "max_location_exposure": 10,
  "entry_slippage_rate": 0.0,
  "allow_stale_price_fallback": false,
  "model_version": "baseline_precip_v1"
}
```

Set `model_version` to `logistic_precip_v1` to run the same paper-only workflow with the fixed-coefficient logistic regression model. The default remains `baseline_precip_v1`.

Run a no-trade rehearsal through the same workflow:

```http
POST /paper-runner/rehearsal
Content-Type: application/json

{
  "keywords": ["rain", "precipitation", "snow"],
  "discovery_limit": 25,
  "process_limit": 10,
  "max_trades": 3,
  "quantity": 1,
  "min_liquidity": 100,
  "max_spread": 0.15
}
```

Rehearsal behavior:

- Forces no-trade mode even if the request body says otherwise.
- Discovers, validates, parses, forecasts, predicts, and evaluates EV through the normal runner path.
- Reports `actionable_recommendations` and `expected_paper_trades`.
- Applies duplicate-trade, freshness, max-trade, and paper portfolio limits before counting expected paper trades.
- Persists the run record for inspection, but creates no `paper_trades`.

Read recent persisted runs:

```http
GET /paper-runner/runs
GET /paper-runner/runs/{run_id}
```

Read an aggregated public-market validation report:

```http
GET /paper-runner/diagnostics
GET /paper-runner/diagnostics?source=polymarket&limit=20
```

Current behavior:

- Summarizes recent paper-run counts for discovered, processed, parsed, forecasted, predicted, recommended, and simulated paper-traded markets.
- Groups skip reasons into readable categories such as price data, eligibility filters, parser, geocoding, provider/workflow errors, and paper-trading controls.
- Separates interval precipitation contracts from generic parser failures so public dry-run diagnostics show when a market needs interval probability modeling rather than one-sided threshold parsing.
- Prioritizes precipitation threshold candidates ahead of broad weather false positives, such as space-weather event-count markets, when selecting the next stored markets to process.
- Skips stale price snapshots and stale forecast snapshots using configurable freshness limits.
- Skips markets whose target weather window has already started or elapsed, because the current paper runner uses forecast-only modeling rather than observed-to-date plus remaining forecast data.
- Applies conservative paper portfolio limits before creating simulated trades: max open trades, total simulated exposure, per-market exposure, and per-location exposure.
- Optionally applies paper entry slippage to simulated fills while preserving the quoted entry price in `signal_snapshot_json`.
- Reports market source price-status counts from persisted `source_diagnostics`, such as `supported`, `partial`, `unsupported`, `stale_supported`, and `fresh_price_required`.
- Reports how many public refresh failures reused a stored binary snapshot through `stale_price_fallbacks_used`.
- Reports unsupported public price reasons captured from market diagnostics, such as non-binary outcomes, missing binary prices, unsupported fresh price payloads, and source refresh failures.
- Returns recent workflow/provider errors with the runner record ID that captured each error.
- Does not refresh public data, call weather providers, create paper trades, or use live execution.

Expected response shape:

```json
{
  "source": "polymarket",
  "run_count": 2,
  "latest_run_ids": [12, 11],
  "discovered": 50,
  "processed": 20,
  "parsed": 3,
  "forecasts_created": 2,
  "predictions_created": 2,
  "recommendations_created": 2,
  "paper_trades_created": 0,
  "skip_reasons": [
    {
      "reason": "missing_coordinates",
      "count": 6,
      "category": "geocoding",
      "label": "Parsed location has no coordinates"
    }
  ],
  "price_status_counts": {
    "partial": 4,
    "supported": 8
  },
  "unsupported_price_reasons": [
    {
      "reason": "non_binary_outcomes",
      "count": 2
    }
  ],
  "error_count": 1,
  "recent_errors": [
    {
      "run_id": 12,
      "message": "market_id=7: provider timeout"
    }
  ]
}
```

## Trading Mode Boundary

These workflows currently cover research and paper trading. Paper mode is the default and must remain available even after live trading is introduced.

See `TRADING_MODES.md`, `LIVE_TRADING_SAFETY.md`, and `EXECUTION_DESIGN.md` for the future execution boundary.

Future live-trading workflows may be added to this backend only after these controls exist:

- Explicit live-mode configuration that defaults off.
- Credential and secret isolation.
- Position and exposure limits.
- Kill-switch behavior.
- Audit logs for live-intent actions.
- Tests proving paper mode cannot place live orders.
- Clear separation between simulated paper trades and real execution records.

Until those controls exist, paper trading is the implementation target for execution-like behavior.

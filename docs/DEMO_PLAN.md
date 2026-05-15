# Demo Plan

## Purpose

The demo should let a reviewer understand WeatherEdge AI quickly. It should show a real backend workflow, not just isolated endpoints.

For copy-paste local commands, use `LOCAL_DEMO.md`. This document focuses on what to show and how to explain it.

Target demo length:

```text
2 to 3 minutes for interview overview
10 minutes for local technical review
```

## Demo Goal

Show that WeatherEdge AI can:

1. Discover or seed a weather prediction market.
2. Parse the market into structured weather terms.
3. Fetch a forecast snapshot.
4. Run a probability model.
5. Evaluate expected value against market prices.
6. Create a simulated paper trade.
7. Replay resolved outcomes and paper trades through backtesting.
8. Explain what safety controls are required before live trading is enabled.

The frontend paper-trading workspace can now be used as the visual entry point for the paper demo. Run the safe mock/fixture workflow from the console, then inspect the refreshed workflow, signal, paper-trade, outcome-log, and evaluation sections. The same console can run a guarded public paper pass, defaulting to dry-run mode. The backend API remains the source of truth for the workflow.

## Demo Setup

From the repository root:

```powershell
cd C:\weatherEdgeAI
Copy-Item .env.example .env
docker compose up -d
docker compose ps
```

From the backend directory:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\activate
alembic upgrade head
uvicorn app.main:app --reload
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

Expected:

```json
{
  "status": "ok",
  "service": "WeatherEdge AI"
}
```

Optional read-only dashboard:

```powershell
cd C:\weatherEdgeAI\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` after the backend is running. The workspace reads health, dashboard summary, paper-trade, and resolved-outcome data. Its run console calls only paper-safe endpoints: `POST /demo/paper-workflow` and `POST /paper-runner/run-once`.

For a scripted walkthrough, run:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\quick_demo.py
```

This is the fastest deterministic command for local review. It uses an
in-memory SQLite database, runs the paper workflow, runs the seed backtest,
reads the dashboard summary, and avoids PostgreSQL, Docker, frontend setup, and
network dependencies.

For a database-backed scripted walkthrough, run:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\demo_workflow.py
```

The script uses mock market discovery and a deterministic forecast fixture by default so the core paper-trading workflow is repeatable. It still exercises the FastAPI route layer and writes to the configured database. For a no-PostgreSQL smoke check, use `--sqlite-memory`.

## Recommended Demo Data

Use mock market discovery for reliable local demos:

```json
{
  "source": "mock",
  "keywords": ["rain", "weather"],
  "limit": 10
}
```

Mock data is acceptable for the portfolio demo because it keeps the workflow deterministic. The project should still support public market discovery as a real integration path.

## Main Demo Script

### 1. Discover Markets

```http
POST /markets/discover
```

Explain:

- The system discovers weather-related markets.
- Discovery is idempotent.
- Raw payloads are preserved for debugging.

Show:

```http
GET /markets
```

### 2. Parse A Market

```http
POST /markets/{market_id}/parse
```

Explain:

- The parser converts market wording into structured fields.
- V1 focuses on one-sided precipitation threshold markets and supports common wording such as "more than", "over", "at least", "or more", "less than", and millimeter thresholds.
- Location coordinates are resolved through a deterministic fixture geocoder for the demo cities.
- Rule-based parsing is intentional because it is inspectable and testable.

Show fields:

- Location.
- Latitude and longitude.
- Metric.
- Operator.
- Threshold.
- Target window.
- Parser version.

### 3. Fetch Forecast

```http
POST /weather/forecast/{parsed_market_id}
```

Explain:

- Forecasts are stored as snapshots.
- Snapshotting makes predictions reproducible.
- Open-Meteo is the initial weather provider.
- Forecast normalization is fixture-tested for missing and malformed values, unit conversion, and raw payload preservation.

Show:

```http
GET /weather/forecast/{parsed_market_id}/latest
```

### 4. Run Prediction

```http
POST /predictions/run/{market_id}
```

Explain:

- The baseline model compares forecast precipitation to the market threshold.
- The prediction stores model version and feature payload.
- This establishes the baseline for future calibration.

Show:

- `model_version`.
- `p_yes`.
- `p_no`.
- `confidence`.
- `features_json`.

### 5. Evaluate Strategy

```http
POST /strategy/evaluate/{market_id}
```

Explain:

- The system compares model probability with market-implied price.
- It calculates edge and expected value.
- Recommendations flow to paper trading first.

Show:

- Market price.
- Model probability.
- Edge.
- Recommendation.
- Paper position size.

### 6. Create Paper Trade

```http
POST /paper-trades
```

Explain:

- This creates a simulated position from a recommendation.
- No real order is placed in the current demo flow.
- Paper mode is the default and remains the record used for paper-trade evaluation.

Show:

```http
GET /paper-trades
```

### 7. Show Market Detail

```http
GET /markets/{market_id}
```

Explain:

- The detail view ties together the latest parsed market, price snapshot, prediction, and EV recommendation.
- This is the easiest endpoint for reviewers to understand the current market state.

### 8. Run Backtest Replay

```http
POST /backtests/run
```

Use:

```json
{
  "start_date": "2026-05-01",
  "end_date": "2026-05-10",
  "model_version": "baseline_precip_v1",
  "seed_fixtures": true
}
```

Explain:

- The replay joins stored predictions to resolved outcomes.
- It reports probability-quality metrics: Brier score, log loss, win rate, and calibration buckets.
- It reports paper-trade summaries for linked recommendations: trade count, settlement PnL, ROI, and max drawdown.
- The seed sample is intentionally tiny, so the result proves workflow mechanics rather than strategy profitability.

## Interview Narrative

Short version:

```text
WeatherEdge AI is a live-trading-capable backend in progress for weather prediction markets, with paper trading implemented first. It discovers markets, parses the question into structured weather targets, pulls forecast snapshots, estimates the chance of resolution, compares that probability against market prices, and records simulated trades. The goal is to validate the research pipeline before enabling real execution.
```

Technical version:

```text
The key design choice is snapshotting. Market prices, weather forecasts, predictions, recommendations, paper trades, and resolved outcomes are all stored as records. That gives the system provenance: every model output can be traced back to the exact parsed market and forecast snapshot used, and the same records support Brier score, log loss, calibration buckets, and paper-trade evaluation.
```

## What To Emphasize

- Paper trading is the current/default execution mode.
- The system is designed for research, validation, portfolio review, and later safety-gated live execution.
- The backend has a real domain workflow.
- Model outputs are versioned and reproducible.
- Backtesting and calibration are implemented in an initial replay form.
- Live trading requires explicit mode configuration, credentials isolation, limits, audit logs, monitoring, and kill-switch behavior before it is enabled.

## Current Demo Limitations

- The frontend workspace shows workflow status, latest signals, backtest/calibration context, stored opportunities, open and historical paper trades, outcome logs, and public paper-run history. It includes safe paper-demo and guarded public paper-run controls, but no live-trading controls.
- Backtesting currently uses persisted outcomes or deterministic seed fixtures for reliable demos. Open-Meteo archive outcome resolution is implemented for parsed precipitation markets, and an optional credential-gated NOAA/NCEI CDO daily `PRCP` client is available for manual outcome resolution when `NOAA_CDO_TOKEN` is configured.
- Parser support is limited to V1 one-sided precipitation threshold wording, with clearer failures for unsupported questions, missing thresholds, unsupported units, and interval/range contracts.
- Location support uses a deterministic fixture geocoder for a few demo cities and should later add a broader provider.
- Forecast normalization has initial fixture-backed edge-case coverage and should continue expanding with captured provider payloads.
- Market price snapshot ingestion has fixture coverage for several public payload shapes, but should continue expanding as unsupported real responses are captured.
- Seed backtest samples are too small to support profitability claims.

Be direct about these limitations in interviews. They are roadmap items, not hidden defects.

## Portfolio Polish Checklist

Before calling the project portfolio-ready:

- Fresh setup works from README instructions.
- Tests pass with PostgreSQL running through Docker Compose and migrations applied.
- Demo sequence works with mock data.
- Demo sequence works with public data when network access is available.
- API workflow docs match actual responses.
- Backtest report returns real metrics.
- README includes a short architecture overview.
- Resume bullets match implemented behavior.

## Future Live-Trading Readiness Demo

Do not demo live trading until the safety foundation exists.

The right message before live execution exists is:

```text
This project validates the research pipeline through paper trading first. Live trading is part of the backend direction, but it is blocked until credentials, order management, audit logs, monitoring, limits, kill switches, and tests are implemented.
```

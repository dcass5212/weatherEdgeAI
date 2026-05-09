# WeatherEdge AI

WeatherEdge AI is a portfolio-grade AI/ML backend for weather-related prediction markets. It discovers weather markets, parses market questions into structured weather targets, fetches weather forecasts, estimates market resolution probabilities, compares those probabilities with market prices, supports paper-trading research, and evaluates predictions through backtesting and calibration.

Paper trading is the required first execution mode and remains the default for local development, tests, demos, and strategy validation. Live trading may be added later in this backend only after safety controls exist, including explicit live-mode configuration, credential isolation, position limits, audit logging, kill-switch behavior, and tests that prove paper mode cannot place real orders.

## Portfolio Goal

The project is designed to demonstrate clean backend architecture, testable data pipelines, probability modeling, expected value analysis, and responsible AI/ML engineering.

The portfolio story is: build a reproducible backend that can discover, score, backtest, and paper trade weather markets first; then extend the same architecture toward live trading with clear safety gates and operational controls.

## Architecture Overview

WeatherEdge AI is organized around a persisted research workflow:

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
  -> Backtest replay metrics
```

The API modules expose the workflow, while small adapter modules isolate public market data, weather forecasts, geocoding, probability modeling, strategy logic, and observed-outcome resolution. Raw provider payloads are preserved alongside normalized records so predictions and backtests can be traced back to their source inputs.

## Tech Stack

- Python 3.12+
- FastAPI
- Pydantic and pydantic-settings
- SQLAlchemy ORM
- PostgreSQL
- psycopg2-binary
- httpx
- pandas
- pytest
- Docker Compose

## Setup

From Windows PowerShell:

```powershell
cd C:\weatherEdgeAI\backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Copy the environment template before running the app:

```powershell
cd C:\weatherEdgeAI
Copy-Item .env.example .env
```

## Run Database

Start the local PostgreSQL container:

```powershell
cd C:\weatherEdgeAI
docker compose up -d
```

Check container status:

```powershell
cd C:\weatherEdgeAI
docker compose ps
```

View database logs:

```powershell
cd C:\weatherEdgeAI
docker compose logs postgres
```

Stop the database while keeping the persisted Docker volume:

```powershell
cd C:\weatherEdgeAI
docker compose stop
```

Remove the container and network while keeping the named data volume:

```powershell
cd C:\weatherEdgeAI
docker compose down
```

The Compose service runs PostgreSQL 16 in a container named `weatheredge-postgres` and exposes it at `localhost:5432`. The default local connection string is:

```text
postgresql+psycopg2://weatheredge:weatheredge@localhost:5432/weatheredge
```

## Run Migrations

Create or update the local PostgreSQL schema with Alembic before starting the API:

```powershell
cd C:\weatherEdgeAI\backend
alembic upgrade head
```

Alembic reads `DATABASE_URL` through the same application settings used by FastAPI. To create a new schema revision after ORM changes:

```powershell
cd C:\weatherEdgeAI\backend
alembic revision --autogenerate -m "describe schema change"
```

## Run Backend

```powershell
cd C:\weatherEdgeAI\backend
uvicorn app.main:app --reload
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "WeatherEdge AI"
}
```

## Run Tests

```powershell
cd C:\weatherEdgeAI\backend
pytest
```

## Run Scripted Demo

After PostgreSQL is running and migrations are applied:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\demo_workflow.py
```

For a quick smoke run without PostgreSQL:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory
```

Expected smoke-demo shape:

```text
discovery: discovered=2, created=2, updated=0, price_snapshots_created=2
parsed: location_name='New York City', operator='>', threshold_value=1.0, threshold_unit='inch'
forecast: forecast_source='demo_fixture', forecast_precip_total=1.6, forecast_precip_unit='inch'
prediction: model_version='baseline_precip_v1', p_yes=0.75, p_no=0.25
strategy: recommendation='PAPER_BUY_YES', market_price_yes=0.44, edge_yes=0.31
paper_trade: side='YES', entry_price=0.44, quantity=10.0, status='OPEN'
```

Run the deterministic seed-fixture backtest through the API after the server is running:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/backtests/run `
  -ContentType "application/json" `
  -Body '{"start_date":"2026-05-01","end_date":"2026-05-10","model_version":"baseline_precip_v1","seed_fixtures":true}'
```

## Key Docs

- `AGENTS.md`: operating instructions for Codex and future contributors.
- `docs/ROADMAP.md`: current project plan and priorities.
- `docs/LOCAL_DEMO.md`: copy-paste local demo workflow.
- `docs/DATA_SOURCES.md`: market, forecast, geocoding, and observed-outcome provider boundaries.
- `docs/TRADING_MODES.md`: paper, live, and read-only mode rules.
- `docs/LIVE_TRADING_SAFETY.md`: controls required before live execution.
- `docs/BACKTESTING_SPEC.md`: replay, metrics, and evidence requirements.

## Current Scope

V1 starts with precipitation threshold markets, such as:

- Will New York City get more than 1 inch of rain on May 5?
- Will Chicago receive at least 0.5 inches of rain tomorrow?

The current backend includes SQLAlchemy persistence models, Pydantic response schemas, mock and public-style market discovery, a precipitation market parser, forecast snapshots, a baseline precipitation probability model, EV strategy evaluation, simulated paper trades, resolved outcomes, and backtest replay metrics.

Market discovery now uses the public Polymarket-style Gamma API by default through `POST /markets/discover`. For local demos or tests without network access, pass `"source": "mock"` in the request body.

Market detail reads include a computed `workflow_status` object that shows completed pipeline steps and the next recommended backend action, such as `create_forecast`, `run_prediction`, or `evaluate_strategy`.

Discovered markets and price refresh attempts store `source_diagnostics` so public data integration gaps are visible from API reads. Polymarket-sourced price refreshes use fresh public source payloads and can combine fresh token price maps with stored Gamma market context when the price response omits outcome/token metadata. Manual or fixture-backed markets can still refresh from stored payloads. Diagnostics identify supported or missing metadata, binary prices, top-of-book data, liquidity, volume, status, and resolution fields without enabling authenticated trading.

Market parsing does not create demo price snapshots. Strategy evaluation depends on price records from market discovery or the explicit price refresh endpoint so recommendations can be traced back to source payloads.

Forecast snapshots now use Open-Meteo through `POST /weather/forecast/{parsed_market_id}`. Parsed markets need latitude and longitude; the V1 parse route resolves New York City, NYC, New York, and Chicago through a deterministic fixture geocoder by default. A broader Open-Meteo geocoding provider is implemented behind the same adapter and can be enabled for manual runs with `GEOCODING_PROVIDER=open_meteo`.

Backtesting now supports persisted predictions joined to resolved outcomes, plus a deterministic seed-fixture replay. Reports include prediction count, resolved outcome count, win rate, Brier score, log loss, calibration buckets, sample-size notes, coverage diagnostics, EV recommendation count, paper-trade count, settlement PnL, paper ROI, and max drawdown.

Observed weather outcomes can be resolved from Open-Meteo archive data for parsed precipitation markets. The resolver can also use a credential-gated NOAA/NCEI CDO daily `PRCP` client when `NOAA_CDO_TOKEN` is configured. NOAA is optional, mocked in tests, and not required for local demos.

Manual NOAA outcome resolution uses the same resolved-outcome endpoint:

```json
{
  "market_id": 1,
  "resolution_provider": "noaa_cdo_daily"
}
```

See `docs/API_WORKFLOWS.md` and `docs/DATA_SOURCES.md` for setup, failure modes, and current NOAA station-selection limitations.

## Backend Endpoints

- `GET /health`
- `GET /markets`
- `POST /markets`
- `GET /markets/{market_id}`
- `POST /markets/discover`
- `POST /markets/{market_id}/price-snapshots/refresh`
- `POST /markets/{market_id}/parse`
- `POST /weather/forecast/{parsed_market_id}`
- `GET /weather/forecast/{parsed_market_id}/latest`
- `POST /predictions/run/{market_id}`
- `GET /predictions/{market_id}`
- `GET /predictions/{market_id}/latest`
- `POST /strategy/evaluate/{market_id}`
- `GET /strategy/opportunities`
- `POST /paper-trades`
- `GET /paper-trades`
- `POST /paper-trades/{paper_trade_id}/close`
- `POST /backtests/run`
- `POST /backtests/resolved-outcomes`
- `GET /backtests/resolved-outcomes`

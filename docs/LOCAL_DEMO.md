# Local Demo

## Purpose

This is the copy-paste local demo path. It should remain deterministic and use paper mode by default.

## Start Services

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

Useful Docker commands from the repository root:

```powershell
docker compose logs postgres
docker compose stop
docker compose up -d
docker compose down
```

`docker compose stop` stops PostgreSQL but keeps the persisted database volume. `docker compose down` removes the container and network while keeping the named volume unless `--volumes` is also passed.

Health check:

```http
GET http://127.0.0.1:8000/health
```

Expected:

```json
{
  "status": "ok",
  "service": "WeatherEdge AI"
}
```

## Frontend Dashboard

The first dashboard displays recent market workflow status, compact source diagnostics, compact latest signal values, backtest/calibration metrics, stored paper-buy opportunities, open paper trades, and recent public paper-runner history from `GET /dashboard/summary`. Recoverable public price-refresh failures that continue from stored discovery-time prices are labeled as `using stored price` instead of a hard source failure. It includes a `Run Paper Demo` button that calls `POST /demo/paper-workflow` to run a deterministic mock/fixture workflow and create a simulated paper trade. It also includes a `Run Public Dry Run` button that calls `POST /paper-runner/run-once` with `dry_run: true`, so public discovery and scoring can be inspected without creating trades. It does not expose live trading.

Start FastAPI first, then run the frontend from a second terminal:

```powershell
cd C:\weatherEdgeAI\frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The frontend uses the Vite `/api` proxy to reach `http://127.0.0.1:8000`, so backend CORS configuration is not required for this local read-only pass.

## Scripted Demo

After PostgreSQL is running and migrations are applied, run the full paper-trading workflow from the backend directory:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\demo_workflow.py
```

The script calls the FastAPI routes in-process, uses mock market discovery, patches the forecast step to a deterministic demo fixture by default, runs prediction and EV evaluation, and creates a paper trade when the strategy returns a paper-buy signal.

Expected output shape:

```text
health: status='ok', service='WeatherEdge AI'
discovery: discovered=2, created=2, updated=0, price_snapshots_created=2
market: id=1, source_market_id='mock-nyc-rain-tomorrow'
parsed: id=1, location_name='New York City', operator='>', threshold_value=1.0, threshold_unit='inch'
forecast: id=1, forecast_source='demo_fixture', forecast_precip_total=1.6, forecast_precip_unit='inch'
prediction: id=1, model_version='baseline_precip_v1', p_yes=0.75, p_no=0.25
strategy: id=1, recommendation='PAPER_BUY_YES', market_price_yes=0.44, edge_yes=0.31
paper_trade: id=1, side='YES', entry_price=0.44, quantity=10.0, status='OPEN'
market_detail: latest_price_snapshot_id=1, latest_forecast_snapshot_id=1, latest_prediction_id=1, latest_ev_recommendation_id=1, latest_paper_trade_id=1, next_action='monitor_paper_trade'
```

For a smoke demo that does not require PostgreSQL, use a temporary in-memory SQLite database:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory
```

To call Open-Meteo instead of the deterministic forecast fixture:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\demo_workflow.py --use-open-meteo
```

Location geocoding stays fixture-backed by default so the local demo is deterministic. For manual public-market experiments with broader locations, set `GEOCODING_PROVIDER=open_meteo` in `.env` before starting the API.

## Backtest Replay Demo

After the API is running, seed and replay a deterministic historical-like backtest:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/backtests/run `
  -ContentType "application/json" `
  -Body '{"start_date":"2026-05-01","end_date":"2026-05-10","model_version":"baseline_precip_v1","seed_fixtures":true}'
```

The response should include:

- `num_predictions` and `num_resolved_outcomes`
- `win_rate`
- `brier_score` and `log_loss`
- `calibration_buckets`
- `sample_size_note`
- `ev_recommendation_count` and `paper_trade_count`
- `paper_total_pnl`, `paper_roi`, and `max_drawdown`

Representative seed-fixture values:

```json
{
  "num_predictions": 3,
  "num_resolved_outcomes": 3,
  "win_rate": 0.666667,
  "brier_score": 0.194167,
  "paper_total_pnl": 5.8,
  "paper_roi": 0.408451,
  "max_drawdown": 4.5,
  "sample_size_note": "Very small sample; use metrics only to verify the replay workflow."
}
```

## Public-Market Paper Runner

Use this only after PostgreSQL is running and migrations are applied. The command performs one guarded paper-only pass over public weather markets:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --max-trades 3 --quantity 1 --min-liquidity 100 --max-spread 0.15
```

For a rehearsal that creates predictions and EV recommendations but no paper trades:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run
```

For a bounded overnight run, keep the command explicit:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --interval-minutes 30 --max-hours 10 --max-trades 3 --quantity 1 --min-liquidity 100 --max-spread 0.15
```

Current behavior:

- Discovers public Polymarket-style weather markets.
- Runs once by default; loop mode is enabled only with `--interval-minutes` and requires `--max-hours` or `--max-runs`.
- Refreshes public price snapshots unless `--no-refresh-prices` is set.
- Skips markets without binary prices, coordinates, eligible liquidity, or eligible spread.
- Parses supported precipitation markets and resolves coordinates through the configured geocoding adapter.
- Fetches Open-Meteo forecasts, runs the baseline model, evaluates EV, and creates capped simulated paper trades.
- Skips an actionable side when an open paper trade already exists for that market and side.
- Prints discovery, workflow, skip, and error counts.
- Persists each pass in `paper_runner_runs` with the config, status, counts, skip reasons, errors, and compact report.
- Surfaces recent persisted runs in the frontend dashboard, including dry-run status, workflow counts, skip reasons, and errors.
- Does not place real orders, sign transactions, use authenticated trading APIs, or create live execution records.

You can also trigger one one-shot pass through the API:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/paper-runner/run-once `
  -ContentType "application/json" `
  -Body '{"dry_run":true,"max_trades":1,"quantity":1,"min_liquidity":100,"max_spread":0.15}'
```

Inspect persisted runs:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/paper-runner/runs
```

## Optional NOAA Outcome Resolution

The local demo does not require NOAA. Use this only for manual observed-outcome experiments after a market has been parsed and has coordinates plus target dates.

Configure `.env`:

```env
NOAA_CDO_BASE_URL=https://www.ncei.noaa.gov/cdo-web/api/v2
NOAA_CDO_TOKEN=your_token_here
```

Resolve a parsed market with NOAA/NCEI CDO daily precipitation:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/backtests/resolved-outcomes/resolve-weather `
  -ContentType "application/json" `
  -Body '{"market_id":1,"resolution_provider":"noaa_cdo_daily"}'
```

Then inspect the persisted outcome:

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri http://127.0.0.1:8000/backtests/resolved-outcomes?market_id=1
```

Open-Meteo remains the default:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/backtests/resolved-outcomes/resolve-weather `
  -ContentType "application/json" `
  -Body '{"market_id":1}'
```

## Demo Sequence

Use mock discovery for deterministic local review.

Mock discovery creates deterministic market price snapshots. Manually created markets do not receive demo prices during parsing; use discovery or the explicit price refresh endpoint before strategy evaluation.

### 1. Discover Markets

```http
POST http://127.0.0.1:8000/markets/discover
Content-Type: application/json

{
  "source": "mock",
  "keywords": ["rain", "weather"],
  "limit": 10
}
```

### 2. List Markets

```http
GET http://127.0.0.1:8000/markets
```

Copy a returned `id` as `{market_id}`.

### 3. Parse Market

```http
POST http://127.0.0.1:8000/markets/{market_id}/parse
```

Copy the returned `id` as `{parsed_market_id}`.

### 4. Fetch Forecast Snapshot

```http
POST http://127.0.0.1:8000/weather/forecast/{parsed_market_id}
```

### 5. Run Prediction

```http
POST http://127.0.0.1:8000/predictions/run/{market_id}
```

### 6. Evaluate Strategy

```http
POST http://127.0.0.1:8000/strategy/evaluate/{market_id}
```

Copy the returned recommendation `id` if present in the response.

### 7. Create Paper Trade

```http
POST http://127.0.0.1:8000/paper-trades
Content-Type: application/json

{
  "recommendation_id": 1,
  "quantity": 10
}
```

Replace `1` with the actual recommendation ID.

### 8. Inspect Results

```http
GET http://127.0.0.1:8000/markets/{market_id}
```

The market detail response includes `workflow_status` plus the latest parsed market, price snapshot, forecast snapshot, prediction, EV recommendation, and paper trade when present. During a normal demo, `next_action` should advance through `parse_market`, `create_forecast`, `run_prediction`, `evaluate_strategy`, `ready_for_paper_trade`, and then `monitor_paper_trade` after a simulated trade exists.

```http
GET http://127.0.0.1:8000/strategy/opportunities
```

```http
GET http://127.0.0.1:8000/paper-trades
```

### 9. Inspect Dashboard Summary

```http
GET http://127.0.0.1:8000/dashboard/summary
```

This endpoint returns recent market workflow rows, compact latest parsed target/forecast/model/price/EV values, a compact backtest/calibration summary, paper-buy opportunities, and open paper trades for the frontend dashboard.

To seed the same paper demo workflow from the API:

```http
POST http://127.0.0.1:8000/demo/paper-workflow
Content-Type: application/json

{
  "quantity": 10
}
```

### 10. Run Backtest Replay

```http
POST http://127.0.0.1:8000/backtests/run
Content-Type: application/json

{
  "start_date": "2026-05-01",
  "end_date": "2026-05-10",
  "model_version": "baseline_precip_v1",
  "seed_fixtures": true
}
```

## Demo Notes

- Paper trading is the default execution mode.
- No real order should be placed during this demo.
- The frontend dashboard has one safe `Run Paper Demo` action. Broader workflow controls are still planned.
- Public market discovery can be demonstrated later, but mock discovery is preferred for reliable portfolio review.
- Observed-weather resolution is implemented for Open-Meteo archive precipitation markets and optional credential-gated NOAA/NCEI CDO daily `PRCP` observations.
- NOAA/NCEI CDO requires `NOAA_CDO_TOKEN`, is mocked in tests, and is not required for this demo.
- Backtest seed fixtures are intentionally small; use them to demonstrate replay mechanics, not trading performance.
- Before portfolio review, verify `.\.venv\Scripts\pytest.exe` passes with PostgreSQL running through Docker Compose and migrations applied.

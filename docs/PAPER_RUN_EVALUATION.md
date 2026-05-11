# Paper Run Evaluation

## Purpose

Use this runbook before and after a bounded multi-day paper-market run. The goal is to collect inspectable paper-trading evidence, not to claim trading performance from a small sample.

## Pre-Run Checks

From the backend directory, run:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\pre_run_smoke.py
```

The smoke command verifies:

- Live execution is disabled.
- PostgreSQL is reachable.
- Required workflow tables are present.
- Seed-fixture replay can produce evaluation metrics.
- Paper-runner history is readable.

To require at least one previous paper-runner record before starting a longer loop:

```powershell
.\.venv\Scripts\python.exe scripts\pre_run_smoke.py --require-runner-history
```

## Recommended Multi-Day Command

Before starting the loop, run a no-trade rehearsal:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --rehearsal --min-liquidity 100 --max-spread 0.15
```

Review `actionable_recommendations`, `expected_paper_trades`, skip reasons, and errors. If expected trades are zero, fix data-quality or eligibility issues before running for multiple days.

Start conservatively:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --interval-minutes 30 --max-hours 72 --max-trades 3 --quantity 1 --min-liquidity 100 --max-spread 0.15
```

Keep interval/range precipitation contracts disabled for the first run unless the run is explicitly about experimental interval behavior.

The overnight runner now requires fresh public prices by default. Only opt into
stored-price fallback with `--allow-stale-price-fallback` if the run is explicitly
about replaying older binary snapshots.

The runner defaults to freshness guards so stale inputs do not become paper trades:

- `PAPER_RUNNER_MAX_PRICE_AGE_MINUTES=120`
- `PAPER_RUNNER_MAX_FORECAST_AGE_HOURS=12`

Skip reasons such as `price_snapshot_stale`, `forecast_snapshot_stale`, `target_window_started`, and `target_window_elapsed` should be treated as data-quality signals, not strategy results. A started monthly or daily target window needs observed-to-date weather plus a remaining forecast before it is suitable for paper-trading evaluation.

The first recommended paper portfolio limits are intentionally conservative:

- `max_open_trades`: 5
- `max_total_exposure`: 25
- `max_market_exposure`: 5
- `max_location_exposure`: 10

This roughly models a small research bankroll where only a quarter of capital is exposed at once, no single market can dominate the paper account, and related weather bets in one location stay capped. These are paper-mode realism controls only; live trading would require separate tested risk controls, account constraints, and kill-switch behavior.

Entry slippage defaults to `0.0` to preserve historical demo behavior. To stress test paper fills before a longer run:

```powershell
.\.venv\Scripts\python.exe scripts\paper_market_runner.py --rehearsal --entry-slippage-rate 0.02
```

When slippage is enabled, `paper_trades.entry_price` is the simulated fill price. The quoted price, fill price, slippage rate, and slippage cost remain inspectable in `signal_snapshot_json.paper_trade`.

## Outcome Resolution

For the normal post-run maintenance loop, use the automation script from the
backend directory:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\python.exe scripts\research_maintenance.py --start-date 2026-05-01 --end-date 2026-05-10 --limit 100
```

The script:

- Previews outcome-resolution eligibility.
- Resolves eligible completed weather markets through the selected observed-weather provider.
- Settles matching open paper trades by default.
- Generates an evidence report for the selected date window.
- Writes timestamped JSON logs under `backend/research_logs/`.

Use `--preview-only` to log eligibility and evidence without calling observed-weather providers or creating outcomes. Use `--no-settle-open-trades` only when you need to inspect outcomes before settlement.

After target weather windows have completed, preview which parsed markets are eligible:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/backtests/resolved-outcomes/eligibility-preview?resolution_provider=open_meteo_archive&limit=100"
```

The preview is read-only and categorizes markets as `ready`, `not_ready`, `missing_coordinates`, `missing_target_window`, `already_resolved`, or `skipped`.

Markets with `missing_target_window` cannot be resolved automatically. The parser supports daily targets such as `tomorrow` and `on May 5`, plus month windows such as `in May`; if older parsed records lack target dates, a fresh paper-runner pass can create newer parsed records with complete target windows before outcome resolution.

Resolve eligible parsed markets in batch:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/backtests/resolved-outcomes/resolve-weather-batch `
  -ContentType "application/json" `
  -Body '{"resolution_provider":"open_meteo_archive","limit":100,"settle_open_trades":true}'
```

Batch resolution skips markets that already have an outcome for the selected provider by default. It also skips parsed markets whose target window has not completed. When an outcome is created, open paper trades for that market are settled at `1.0` for the winning side and `0.0` for the losing side.

## Evidence Report

Use the evidence report after resolving outcomes:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/evaluation/evidence-report?start_date=2026-05-01&end_date=2026-05-10&model_version=baseline_precip_v1"
```

The report includes:

- Paper-runner counts, skips, and errors.
- Prediction, outcome, and paper-trade counts.
- Paper trade lifecycle counts: recommended buy signals, recommended-but-not-traded signals, open, resolved, manually closed, unresolved, and unresolved past target window.
- Market-implied comparison coverage: evaluated predictions, predictions with linked market YES prices, missing market comparisons, and coverage ratio.
- Backtest metrics and calibration buckets.
- Gross/net paper PnL with fee and slippage assumptions.
- Baseline comparisons against always-50% and market-implied probabilities when linked market prices exist.
- A sample-size gate: `insufficient_sample`, `early_signal`, or `reviewable_sample`.

Each paper trade stores `signal_snapshot_json` at entry time. Use it to inspect why the simulated trade happened: parsed target, forecast precipitation, model probability, market price, edge, liquidity, spread, recommendation reason, and runner config.

## Algorithm Refinement Methodology

The paper-run process should collect broad research evidence while keeping the simulated paper portfolio realistic.

1. Use rehearsal and dry-run passes for broad signal collection. These runs create parsed targets, forecasts, predictions, EV recommendations, skip reasons, and expected-trade counts without opening many simulated positions.
2. Raise paper portfolio caps gradually for data collection. Moderate increases such as 25 open trades can improve coverage, but very large unconstrained exposure makes paper PnL less representative of a strategy.
3. Analyze all evaluated recommendations, not only opened paper trades. The core ML dataset is market features, forecast features, model probability, market price, edge, recommendation, skip reason or trade decision, and final outcome.
4. Separate research candidates from the paper portfolio. Research records can be broad; paper trades should represent a constrained execution policy with liquidity, spread, duplicate-trade, and exposure limits.
5. Resolve outcomes on a schedule before interpreting results. Evidence reports, calibration, Brier score, log loss, market-implied comparisons, unresolved counts, and lifecycle counts should drive algorithm changes before any future live-trading work.

This methodology is the minimum standard for deciding whether a future model or trade-selection rule is stronger than the current baseline. Live trading remains blocked until paper evidence, backtesting, and live-execution safety controls are in place.

## Interpretation Rules

- Treat `insufficient_sample` as workflow validation and early signal inspection only.
- Do not claim profitability from a few days of paper trades.
- Prefer Brier score, log loss, calibration, coverage, and unresolved-count diagnostics over raw ROI.
- Compare the model against market-implied probability before arguing that it adds value.
- Explain unresolved trades and missing outcomes before interpreting PnL.

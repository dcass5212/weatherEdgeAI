# Changelog

All notable Codex-assisted changes to WeatherEdge AI are documented here after each implementation prompt.

## 2026-05-18

### Added

- Added a tabbed frontend research workspace with overview, markets, paper runs, trades, evidence, and diagnostics views.
- Added frontend reads for `GET /evaluation/evidence-report`, `GET /paper-runner/runs`, and `GET /paper-runner/diagnostics`.
- Added expandable market workflow rows, paper-run detail panels, paper-trade signal snapshot inspection, evidence-report lifecycle metrics, baseline comparison tables, runner funnel diagnostics, skip-reason summaries, price-status summaries, and date/model/source/action filters.
- Added a persistent paper-mode safety strip to the frontend so browser demos clearly show that live execution remains disabled.

### Changed

- Reworked the frontend from a compact status dashboard into a denser paper-trading review workspace while keeping all execution-like controls paper-only.
- Updated README, API workflow docs, local demo docs, demo plan, and roadmap notes for the expanded dashboard behavior.

### Verified

- Ran `npm run build` in `frontend`; TypeScript and Vite production build completed successfully.

## 2026-05-16

### Added

- Added first-pass daily high/low temperature bucket parsing for questions such as `Highest temperature in NYC on May 17 80-81F?` and `Lowest temperature in London on May 17 10C or lower?`.
- Added `baseline_temperature_bucket_v1`, a transparent point-forecast baseline for daily high/low temperature bucket markets with Celsius/Fahrenheit conversion.
- Added default model dispatch so temperature parsed markets use the temperature bucket baseline while precipitation markets keep the precipitation baseline.
- Added public discovery normalization that combines temperature event titles with child bucket labels such as `80-81F`.
- Added focused parser, model, discovery, and paper-runner tests for temperature bucket markets.
- Added partial-window precipitation forecast snapshots that combine Open-Meteo archive observations through yesterday with Open-Meteo forecast precipitation for the remaining target window.
- Added `PAPER_RUNNER_ALLOW_PARTIAL_STARTED_WINDOWS`, paper-runner API support, and CLI `--allow-partial-started-windows` / `--skip-started-windows` controls.
- Added Seattle and Seoul to the deterministic fixture geocoder for current public precipitation market coverage.
- Added focused tests for partial-window forecast construction and started-window runner behavior.

### Changed

- Changed public paper-runner parser skip accounting so opt-in interval precipitation contracts are reported only as `parse_failed_interval_contract`, leaving generic `parse_failed` for unsupported parser misses.
- Changed public paper-runner defaults to search the precipitation-oriented default keyword set, discover up to 50 markets, and process up to 25 candidates per pass.
- Updated docs to distinguish elapsed windows from started-but-active precipitation windows and to describe the combined observed-plus-forecast input.
- Updated the roadmap with planned expansion paths for daily high/low temperature buckets, binary temperature thresholds, daily precipitation thresholds, and snowfall thresholds while keeping those markets out of implemented paper trading for now.
- Reworked the README public paper-runner instructions into a start-to-finish paper bot runbook covering database setup, smoke checks, rehearsal, one-pass runs, overnight loops, outcome maintenance, inspection endpoints, supported market types, and paper-mode guardrails.

### Verified

- Ran `.\.venv\Scripts\pytest.exe tests\test_market_parser.py tests\test_paper_market_runner.py -q`; all 42 focused parser and paper-runner tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_parser.py tests\test_temperature_bucket_model.py tests\test_market_discovery.py tests\test_paper_market_runner.py tests\test_forecast_service.py tests\test_api_paper_runner.py tests\test_paper_market_runner_cli.py -q`; all 99 focused tests passed.
- Ran `.\.venv\Scripts\pytest.exe -q`; all 196 backend tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --rehearsal --allow-interval-contracts --max-trades 3 --quantity 1 --min-liquidity 30 --max-spread 0.5`; the public rehearsal discovered 50 markets, created 5 forecasts/predictions/recommendations, and estimated 3 paper trades without creating simulated trades.
- Ran `.\.venv\Scripts\pytest.exe tests\test_forecast_service.py tests\test_paper_market_runner.py tests\test_api_paper_runner.py tests\test_paper_market_runner_cli.py tests\test_geocoding.py -q`; all 57 focused tests passed.
- Ran `.\.venv\Scripts\pytest.exe -q`; all 189 backend tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --rehearsal --allow-interval-contracts --max-trades 3 --quantity 1 --min-liquidity 30 --max-spread 0.5`; the public rehearsal discovered 50 markets, created 3 forecasts/predictions/recommendations, and estimated 3 paper trades without creating simulated trades.

## 2026-05-13

### Added

- Added persisted-record walk-forward backtesting through `POST /backtests/walk-forward`, including rolling window generation, per-window replay responses, aggregate weighted Brier score, log loss, win rate, paper PnL totals, and interpretation limits for sparse or overlapping windows.
- Added focused backend tests for walk-forward window slicing, aggregate metrics, empty-window reporting, and the API contract.

### Changed

- Updated README, API workflow, backtesting spec, and roadmap documentation for the implemented walk-forward replay workflow and revised near-term priorities.

### Verified

- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py -q`; all 26 focused backtesting tests passed.
- Ran `.\.venv\Scripts\python.exe -m py_compile app\backtesting\schemas.py app\backtesting\backtest_runner.py app\backtesting\walk_forward.py app\api\routes_backtests.py`; compilation succeeded.
- Ran `.\.venv\Scripts\pytest.exe -q`; all 187 backend tests passed.

## 2026-05-12

### Added

- Added Polymarket collection coverage for CLOB-style `liquidityClob`, `volumeClob`, and `volume24hrClob` fields during price snapshot normalization.
- Added focused tests proving default public discovery starts with precipitation-oriented keywords and that CLOB-style liquidity/volume fields populate source diagnostics.
- Added a polished frontend paper-trading workspace with a run console for deterministic demo paper trades and guarded public paper-runner passes.
- Added frontend reads for `GET /paper-trades`, `GET /paper-trades?status=OPEN`, and `GET /backtests/resolved-outcomes` so the UI can show open trades, historical paper trades, and outcome logs.
- Added public paper-run controls for dry-run mode, max simulated trades, quantity, minimum liquidity, and maximum spread while keeping live-trading controls out of the UI.
- Added `VITE_API_PROXY_TARGET` support to the Vite config so local frontend sessions can point at an alternate backend port when `8000` is occupied.

### Changed

- Changed default public market discovery keywords to favor V1 precipitation and weather-measurement terms, reducing noise from broad `weather` search results such as space-weather event-count markets.
- Updated README, API workflow, roadmap, and data-model docs for the refined Polymarket collection behavior.
- Reworked the frontend layout around paper-trading operations, paper ledger totals, market workflow inspection, paper-run history, paper opportunities, paper trades, and resolved outcome logs.
- Updated `README.md`, `docs/API_WORKFLOWS.md`, `docs/LOCAL_DEMO.md`, `docs/DEMO_PLAN.md`, and `docs/ROADMAP.md` to describe the implemented frontend paper-trading workspace.

### Verified

- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py`; all 28 market-discovery tests passed.
- Ran `npm run build` in `frontend`; TypeScript and Vite production build completed successfully.
- Started the frontend dev server and verified `http://127.0.0.1:5173` returned HTTP 200.
- Started a clean SQLite-backed FastAPI instance on `http://127.0.0.1:8001` and a Vite frontend on `http://127.0.0.1:5174`; verified both the page and `/api/dashboard/summary` returned HTTP 200.

## 2026-05-10

### Added

- Added a README section explaining how to run the prediction, strategy, paper-runner, and backtest workflow with different model versions.
- Added `docs/MODEL_TRAINING_WORKFLOW.md` documenting the baseline-read, outcome-resolution, dataset-building, offline logistic-training, replay, and model-promotion process.
- Added `logistic_precip_v1`, a fixed-coefficient logistic regression precipitation model with explicit forecast-vs-threshold features, unit conversion for inch/millimeter thresholds, and versioned prediction output.
- Added a prediction model registry and `model_version` selection for `POST /predictions/run/{market_id}`, keeping `baseline_precip_v1` as the default.
- Added `model_version` selection to the public paper-runner API and CLI so dry runs can compare `baseline_precip_v1` and `logistic_precip_v1` without changing paper-mode defaults.
- Added focused logistic-model and API selection tests.
- Added `scripts/quick_demo.py`, a one-command deterministic demo that runs the paper workflow, seed backtest, dashboard summary, and safety-boundary output in-process against temporary SQLite without Docker, PostgreSQL, frontend setup, or network access.
- Added README, local demo, and demo-plan documentation for the quick demo command.
- Added roadmap follow-up tasks for multi-day evidence loops, walk-forward backtesting, observed-outcome provider quality, calibrated model iteration, public market-data hardening, dashboard evidence views, CI, operational polish, and deferred live-trading safety work.
- Added README local database maintenance commands for inspecting paper research
  table counts, clearing simulated paper trades, clearing paper-run history,
  clearing local outcome evaluation records, and fully resetting the local
  PostgreSQL volume.
- Added `scripts/research_maintenance.py` to preview eligible outcomes, optionally batch-resolve completed weather markets, settle matching open paper trades, generate evidence reports, and write timestamped JSON research logs.
- Added paper-run and modeling documentation for the algorithm refinement methodology: broad signal collection, gradual exposure increases, all-recommendation analysis, research/portfolio separation, and scheduled outcome resolution before model promotion.
- Added month-window parsing for precipitation markets such as `in May` so monthly public contracts can later become outcome-resolution eligible.
- Added Polymarket CLOB market-info client coverage for the current condition-id metadata endpoint.
- Added fallback coverage proving fresh Gamma price refresh can continue when optional CLOB condition-id lookup fails.
- Added explicit stale-price fallback gating for the public paper runner through `PAPER_RUNNER_ALLOW_STALE_PRICE_FALLBACK`, `allow_stale_price_fallback`, `--allow-stale-price-fallback`, and `--require-fresh-prices`.
- Added fresh-price-required diagnostics when public price refresh fails but a stored binary snapshot exists and stale fallback is not enabled.
- Added public paper-runner diagnostics for `stale_price_fallbacks_used` so overnight validation can distinguish fresh-price runs from opt-in stale replays.

### Changed

- Updated the public paper runner to skip target windows that have already started before requesting forecasts, surfacing them as `target_window_started` instead of provider workflow errors.
- Updated forecast fetching to fail closed before Open-Meteo calls when a parsed target window has already started, keeping forecast snapshots limited to future target windows.
- Updated paper-runner docs to explain that started monthly or daily windows need observed-to-date weather plus remaining forecast data before paper evaluation.
- Updated README and paper-run evaluation docs with the post-run research maintenance command.
- Updated the paper runner to reparse existing incomplete parsed-market records when target dates or coordinates are missing, letting newer parser/geocoder improvements repair old workflow records.
- Updated Polymarket price refresh to use a fresh Gamma market payload as the baseline and treat CLOB condition-id metadata as optional enrichment, preventing CLOB lookup failures from blocking otherwise fresh public price refreshes.
- Updated README, API workflow docs, data-source docs, and roadmap notes for the Gamma-first public price refresh behavior.
- Updated the public paper runner to fail closed on public price refresh failures by default instead of automatically continuing from stored discovery-time prices.
- Updated dashboard and runner diagnostics to distinguish `fresh_price_required` from `stale_supported`.
- Updated README, API workflow docs, local demo docs, paper-run evaluation docs, roadmap notes, and `.env.example` to describe the stricter freshness policy and the explicit opt-in fallback flag.

### Verified

- Ran `.\.venv\Scripts\pytest.exe tests\test_logistic_regression_model.py tests\test_baseline_model.py tests\test_api_provenance.py tests\test_paper_market_runner_cli.py tests\test_api_paper_runner.py`; all 33 focused modeling, API, and runner selector tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 183 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_forecast_service.py tests\test_paper_market_runner.py tests\test_api_paper_runner.py tests\test_paper_market_runner_cli.py`; all 48 focused forecast, runner, API, and CLI tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --rehearsal --process-limit 25 --max-trades 25 --quantity 1 --min-liquidity 50 --max-spread 0.25`; the rehearsal completed with `target_window_started=3` and no Open-Meteo 400 workflow errors.
- Ran `.\.venv\Scripts\python.exe -m py_compile scripts\research_maintenance.py`; the maintenance script compiled successfully.
- Ran `.\.venv\Scripts\python.exe -m py_compile scripts\research_maintenance.py app\markets\market_parser.py app\strategy\paper_market_runner.py`; the updated parser, runner, and maintenance script compiled successfully.
- Ran `.\.venv\Scripts\python.exe scripts\research_maintenance.py --help`; command help rendered successfully.
- Ran `.\.venv\Scripts\python.exe scripts\research_maintenance.py --preview-only --start-date 2026-05-01 --end-date 2026-05-10 --limit 20`; preview and evidence JSON logs were written without provider writes.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_parser.py tests\test_paper_market_runner.py`; all 37 focused parser and runner tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py tests\test_paper_market_runner.py`; all 64 focused market, API, and paper-runner tests passed.
- Ran the focused paper-runner, API, dashboard, and config tests after the freshness-policy change.
- Ran `scripts/pre_run_smoke.py` after applying the stricter freshness policy.

## 2026-05-09

### Added

- Added optional paper entry slippage through `PAPER_RUNNER_ENTRY_SLIPPAGE_RATE`, `--entry-slippage-rate`, and the paper-runner API request model.
- Added slipped paper fill behavior with zero default; paper trades preserve quoted entry price, fill entry price, slippage rate, and slippage cost in `signal_snapshot_json.paper_trade`.
- Added focused runner, API, and CLI tests for entry slippage fills, exposure-limit interaction, and argument validation.
- Added market-implied baseline coverage diagnostics to `GET /evaluation/evidence-report`, including evaluated prediction count, linked market-implied count, missing count, coverage ratio, and missing reason.
- Added interpretation-limit messages when market-implied comparison coverage is partial or unavailable.
- Added focused evidence-report tests for full, partial, and missing market-implied baseline coverage.
- Added paper trade lifecycle counts to `GET /evaluation/evidence-report`, including recommended buy signals, recommended-but-not-traded signals, open, resolved, manually closed, unresolved, and unresolved-past-target-window trades.
- Added focused evidence-report tests for paper trade lifecycle counts and unresolved-past-target-window detection.
- Added no-trade paper-run rehearsal support through `POST /paper-runner/rehearsal` and CLI `--rehearsal`.
- Added `actionable_recommendations` and `expected_paper_trades` to paper runner reports so rehearsals estimate useful signal and trade counts after duplicate-trade, freshness, max-trade, and paper portfolio limits.
- Added focused runner, API, and CLI tests proving rehearsal creates no `paper_trades` while estimating expected trades.
- Added `paper_trades.signal_snapshot_json` with an Alembic migration so each simulated entry stores a compact explanation of the parsed target, forecast, prediction, market price, edge, liquidity, spread, recommendation reason, and runner config at creation time.
- Added signal snapshot generation for manual/demo paper trades and public paper-runner-created trades.
- Added tests proving demo and runner-created paper trades persist signal snapshots, and migration coverage for the new column.
- Added read-only `GET /backtests/resolved-outcomes/eligibility-preview` to categorize parsed markets as ready, not ready, missing coordinates, missing target window, already resolved, or skipped before batch outcome resolution.
- Added focused outcome-eligibility preview test coverage for ready, not-ready, missing-data, already-resolved, and duplicate parsed-market cases.
- Added conservative paper portfolio limits to the public paper runner: max open simulated trades, max total simulated exposure, max per-market exposure, and max per-location exposure.
- Added `PAPER_RUNNER_MAX_OPEN_TRADES`, `PAPER_RUNNER_MAX_TOTAL_EXPOSURE`, `PAPER_RUNNER_MAX_MARKET_EXPOSURE`, and `PAPER_RUNNER_MAX_LOCATION_EXPOSURE` settings plus CLI/API overrides.
- Added paper-runner skip reasons for open-trade, total-exposure, market-exposure, and location-exposure portfolio limits.
- Added focused paper-runner, API, and CLI tests for portfolio limit enforcement and override handling.
- Added public paper-runner freshness guards for stale price snapshots, stale forecast snapshots, and already-elapsed target weather windows, with new skip reasons surfaced in runner diagnostics.
- Added `PAPER_RUNNER_MAX_PRICE_AGE_MINUTES` and `PAPER_RUNNER_MAX_FORECAST_AGE_HOURS` settings plus CLI/API overrides for paper-runner freshness limits.
- Added focused paper-runner and CLI tests for stale price/forecast skips and freshness override validation.
- Added outcome-based paper-trade settlement when resolved outcomes are created or observed-weather outcomes are resolved, marking matching open simulated trades `RESOLVED` with binary side payouts.
- Added `POST /backtests/resolved-outcomes/resolve-weather-batch` to resolve eligible completed parsed precipitation markets in batch, skip existing provider outcomes by default, preserve per-market errors, and optionally settle matching open paper trades.
- Added backtest `sample_size_gate` and `baseline_comparisons` against model probability, always-50% probability, and market-implied probability when linked market prices exist.
- Added read-only `GET /evaluation/evidence-report` for multi-day paper-run review, combining runner history, record counts, backtest metrics, baseline comparisons, sample-size gates, unresolved trade counts, and interpretation limits.
- Added `scripts/pre_run_smoke.py` to verify paper-mode safety settings, database connectivity, required tables, seed-fixture replay, and paper-runner history visibility before longer public paper runs.
- Added `docs/PAPER_RUN_EVALUATION.md` as the runbook for pre-run checks, bounded multi-day paper runs, outcome resolution, evidence reporting, and interpretation rules.
- Added configurable backtest paper settlement cost assumptions with `paper_fee_rate` and `paper_slippage_rate`, plus gross PnL, fee cost, slippage cost, net PnL/ROI, and settlement-note response fields.
- Added focused backtesting coverage proving fee and slippage assumptions reduce paper settlement PnL and ROI.
- Added opt-in interval precipitation contract support for `between X-Y` markets, including parser output, baseline interval probabilities, observed-outcome resolution, API parse toggle, paper-runner API field, CLI `--allow-interval-contracts` / `--disable-interval-contracts`, and `PAPER_RUNNER_ALLOW_INTERVAL_CONTRACTS`.
- Added public paper-runner candidate prioritization so V1 precipitation markets are processed before broad weather false positives such as space-weather event-count markets.
- Added London and Hong Kong to the deterministic fixture geocoder so current public precipitation demo markets can progress without external geocoding.
- Added explicit parser and paper-runner diagnostics for interval precipitation contracts, separating markets such as `between 190-200mm` from generic unsupported wording because they require interval probability modeling.
- Added roadmap evidence-readiness follow-ups for rolling backtests, baseline comparisons, fee/slippage assumptions, sample-size gates, compact evidence reporting, paper-trade settlement support, and outcome-resolution tooling.
- Added `GET /paper-runner/diagnostics` to summarize recent public paper-run validation with workflow counts, categorized skip reasons, source price-status counts, unsupported public price reasons, and recent workflow/provider errors.
- Added detailed parser skip codes to the public paper runner, preserving broad `parse_failed` counts while distinguishing not-precipitation, missing-threshold, unsupported-unit, unsupported-wording, and unknown parser failures.
- Added focused paper-runner API and orchestration tests for diagnostics aggregation and detailed parser skip recording.
- Added `source_error_label` to dashboard market summaries so recoverable stale-price fallback can be displayed separately from hard source failures.
- Added recent public paper-runner history to `GET /dashboard/summary`, including status, dry-run mode, workflow counts, skip reasons, and errors.
- Added a frontend `Public Paper Runs` panel and safe `Run Public Dry Run` action backed by `POST /paper-runner/run-once` with `dry_run: true`.
- Added parser support for public one-sided precipitation wording with less-than thresholds and millimeter units, including compact `240mm` style thresholds.
- Added baseline model and observed-outcome support for `<` and `<=` one-sided precipitation operators.
- Added focused parser, baseline model, and outcome-resolution tests for less-than and millimeter threshold behavior.
- Added public paper-runner fallback behavior that continues from the latest stored binary discovery-time price snapshot when read-only public price refresh fails, while preserving `source_refresh_failed` diagnostics, `stale_supported` price status, and the fallback snapshot ID.
- Added regression coverage proving a public refresh 404 no longer discards an otherwise usable stored price snapshot during paper-runner processing.
- Added persisted `paper_runner_runs` records with Alembic migration support for public-market paper runner status, config, summary counts, skip reasons, errors, and compact reports.
- Added `POST /paper-runner/run-once`, `GET /paper-runner/runs`, and `GET /paper-runner/runs/{run_id}` for one-shot public paper-run execution and run-history inspection.
- Added focused tests for completed and failed recorded runner persistence and the paper-runner API contract.
- Added Gamma `public-search` as the primary keyword-based public market discovery path, with event deduplication, child-market expansion, inactive/closed child filtering, and active-event fallback when search returns no candidates.
- Added focused public discovery tests for the `public-search` client path, closed child-market filtering, and active-event fallback.
- Added bounded loop mode to `scripts/paper_market_runner.py` with `--interval-minutes`, `--max-hours`, and `--max-runs`, while keeping one-shot mode as the default.
- Added CLI validation tests proving loop mode requires a stopping bound and preserves one-shot defaults.
- Added `scripts/paper_market_runner.py`, a guarded one-shot public-market paper runner with discovery, optional price refresh, eligibility checks, forecast/model/EV workflow execution, max-trade caps, duplicate open-side checks, and simulated paper-trade creation only.
- Added `app.strategy.paper_market_runner` as an importable orchestration service so the public paper runner can be tested without live network calls.
- Added focused runner tests for creating a capped paper trade, avoiding duplicate open side trades, and skipping markets with missing binary prices, low liquidity, or wide spreads.
- Added compact source diagnostics fields to `GET /dashboard/summary` market rows: `price_status`, `unsupported_reasons`, and `has_public_source_error`.
- Added dashboard API coverage proving supported and partial public source diagnostics are exposed through the summary contract.
- Added frontend market workflow display for supported/partial/unsupported price status, source errors, and compact unsupported reasons.
- Added captured-style partial public price fixtures for non-binary outcomes, outcome/price length mismatches, missing CLOB token context, and empty orderbooks.
- Added focused diagnostics tests proving those partial public payloads preserve liquidity/volume when available while reporting specific unsupported reasons.
- Added captured-style public market-data fixtures for wrapped Gamma-style market payloads and token rows that expose `lastPrice`/`last_price`.
- Added focused discovery and refresh tests proving wrapped public payloads and token last-price rows normalize into source-attributed price snapshots with supported diagnostics.
- Added `POST /demo/paper-workflow`, a paper-only deterministic workflow endpoint for mock discovery, parsing, fixture forecast creation, baseline prediction, EV evaluation, and simulated paper-trade creation.
- Added dashboard `Run Paper Demo` action wired to the paper-only demo endpoint, followed by dashboard refresh.
- Added focused API tests proving the demo workflow creates the full paper chain and reuses existing downstream records on repeated calls.
- Added read-only dashboard evaluation summary support that returns compact backtest metrics, paper replay metrics, calibration buckets, and sample-size context from persisted outcomes when available, with deterministic seed-fixture metrics as a non-mutating fallback.
- Added frontend backtest and calibration panel to the read-only dashboard.
- Added dashboard API tests for the evaluation summary fallback and persisted replay summary.
- Added deterministic one-outcome-per-market selection for backtest replay, using the latest resolved outcome in the requested window and preventing duplicate/corrected outcome records from multiplying predictions, EV counts, or paper-trade settlements.
- Added regression coverage for duplicate resolved outcomes in backtest replay.
- Added explicit `TRADING_MODE` and `LIVE_TRADING_ENABLED` settings with `paper` and `false` defaults, plus tests proving live execution is allowed only when both settings are explicitly enabled.
- Added parser support for explicit-year dates such as `May 5, 2026` and test coverage for reference-clock target-date parsing.
- Added compact latest-signal fields to `GET /dashboard/summary` for parsed target, forecast precipitation, model YES probability, market YES price, YES edge, EV recommendation, and paper-trade status.
- Added inline latest-signal display to the read-only frontend market workflow table.
- Added fixture-backed public market-data coverage for nested CLOB orderbook payloads and nested Gamma-style stats-only payloads.
- Added a read-only Vite + React frontend dashboard under `frontend/` for `GET /dashboard/summary`.
- Added typed frontend API models for health, dashboard market summaries, paper-buy opportunities, open paper trades, and workflow status.
- Added a Vite dev-server `/api` proxy to the FastAPI backend so the first local dashboard pass does not require backend CORS changes.
- Added read-only `GET /dashboard/summary` for recent market workflow rows, paper-buy opportunities, and open paper trades.
- Added dashboard API tests for empty and full paper-trading workflow summary responses.
- Added latest forecast snapshot and latest paper trade fields to market detail responses.
- Added `has_paper_trade` and `monitor_paper_trade` workflow status support for markets with simulated trades.
- Added the new market-detail forecast and paper-trade IDs to the scripted demo output.
- Added focused tests for capped paper-mode risk sizing, including negative/no edge, fractional edge, max-size caps, invalid max size, and YES/NO strategy integration.
- Added backtest `coverage_diagnostics` to report candidate predictions, evaluated prediction/outcome pairs, missing outcomes, unmatched resolved outcomes, and model-version exclusions.
- Added focused backtesting tests for missing-outcome, unmatched-outcome, and mismatched-model diagnostic counts.
- Added a regression test proving market parsing no longer creates demo fallback price snapshots for manually seeded markets.
- Added computed `workflow_status` to market detail responses, including completed pipeline booleans and `next_action`.
- Added route coverage for market workflow status as the pipeline advances from price discovery through paper-trade readiness.
- Added optional `noaa_cdo_daily` observed-weather resolution provider behind the existing resolver interface.
- Added `NoaaCdoClient` with `NOAA_CDO_TOKEN` gating, mocked daily `PRCP` success coverage, and provider-failure handling tests.
- Added `NOAA_CDO_BASE_URL` and optional `NOAA_CDO_TOKEN` settings.

### Changed

- Updated README, API workflow, local demo, trading-mode docs, paper-run evaluation runbook, roadmap, `.env.example`, and changelog for optional paper entry slippage.
- Updated README, API workflow, paper-run evaluation runbook, roadmap, and changelog for market-implied comparison coverage diagnostics.
- Updated README, API workflow, paper-run evaluation runbook, roadmap, and changelog for evidence-report paper trade lifecycle counts.
- Updated README, API workflow, local demo, paper-run evaluation runbook, roadmap, and changelog for paper-run rehearsal reporting.
- Updated README, API workflow, data-model docs, paper-run evaluation runbook, roadmap, and changelog for paper trade signal snapshots.
- Updated README, API workflow, local demo, backtesting spec, paper-run evaluation runbook, roadmap, and changelog for the outcome eligibility preview workflow.
- Updated README, API workflow, local demo, trading-mode docs, paper-run evaluation runbook, roadmap, and `.env.example` for the default paper portfolio limits and their paper-only purpose.
- Updated roadmap priorities to make paper-trading hardening the next highest priority before full multi-day runs.
- Updated README, API workflow, local demo, paper-run evaluation runbook, and environment example docs for paper-runner freshness guards.
- Updated README, API workflow, local demo, data-model, backtesting spec, and roadmap docs for multi-day paper-run readiness, outcome-based settlement, batch resolution, evidence reporting, sample-size gates, and baseline comparisons.
- Updated the dashboard evaluation summary contract and frontend metrics panel to display gross paper PnL, net paper PnL, and paper settlement costs.
- Updated README, API workflow, local demo, backtesting, modeling, and roadmap docs for fee/slippage-aware paper settlement summaries.
- Updated README, API workflow, local demo, data-model, modeling, roadmap, and trading-mode docs for opt-in interval contracts, candidate prioritization, and the new paper-runner configuration toggle.
- Updated API workflow and roadmap docs to describe interval-contract parser diagnostics while keeping interval probability modeling out of scope for the current baseline.
- Updated README, API workflow, roadmap, and data-model docs for the new public paper-run diagnostics report endpoint.
- Updated frontend source diagnostics to label `stale_supported` refresh failures as `using stored price` instead of a red generic source error.
- Updated README, roadmap, API workflow, and local demo docs for dashboard-visible paper-runner history and the public dry-run dashboard action.
- Updated `scripts/paper_market_runner.py` so each CLI pass persists a durable run record while preserving one-shot defaults and bounded loop behavior.
- Updated README, API workflow, local demo, data-model, roadmap, and trading-mode docs for persisted paper runner runs and the new one-shot API.
- Updated README, data-source, API workflow, and roadmap docs for search-oriented public market discovery.
- Updated public paper runner docs with an explicit bounded overnight command and clarified that loop mode cannot run indefinitely without a stop condition.
- Updated README, local demo, API workflow, roadmap, and trading-mode docs for the one-shot public-market paper runner and its paper-only safety boundary.
- Updated dashboard/API workflow, roadmap, and local demo documentation for visible market source diagnostics.
- Updated public market diagnostics to report `non_binary_outcomes`, `outcome_price_length_mismatch`, `missing_token_context`, and `empty_orderbook` for recognizable unsupported price shapes.
- Updated outcome-price normalization so mismatched outcome and price arrays do not fabricate binary YES/NO prices.
- Updated public market-data documentation for the expanded partial-payload diagnostics.
- Updated public market price normalization to read market data from common `market`/`data` wrappers while preserving the original raw payload, and to treat token `lastPrice`/`last_price` fields as usable YES/NO prices.
- Updated public market-data documentation for wrapped Gamma-style payload and token last-price fixture coverage.
- Updated dashboard/frontend copy from strictly read-only to paper-demo capable while preserving the no-live-execution boundary.
- Updated README and demo/API/roadmap docs for the safe paper workflow endpoint and dashboard action.
- Updated dashboard API/frontend contracts and docs for the new `evaluation_summary` field.
- Updated the mock NYC discovery market and scripted demo selector to use a `tomorrow` target date instead of a stale fixed May 5 demo date.
- Updated backtesting, trading-mode, live-safety, data-model, API workflow, README, roadmap, and local-demo documentation for outcome selection, explicit paper-mode settings, and the refreshed mock demo market.
- Removed a stale placeholder backtest report module and an obsolete Open-Meteo normalization TODO.
- Updated dashboard API tests, frontend API types, and dashboard documentation for richer read-only workflow inspection.
- Updated market price normalization to read top-of-book bid/ask levels from nested `book`, `orderbook`, or `order_book` containers and liquidity/volume from nested stats containers.
- Updated `docs/DATA_SOURCES.md` and `docs/ROADMAP.md` for the expanded public market-data fixture coverage.
- Documented frontend setup and the read-only dashboard boundary in `README.md`, `docs/LOCAL_DEMO.md`, `docs/API_WORKFLOWS.md`, `docs/DEMO_PLAN.md`, and `docs/ROADMAP.md`.
- Updated `.gitignore` for frontend dependency and build outputs.
- Documented the dashboard summary endpoint as the first frontend-ready backend contract.
- Updated market detail API docs to describe the full latest paper-trading inspection chain.
- Updated strategy evaluation to use the shared paper risk-sizing helper and include sizing rationale in actionable recommendation reasons.
- Documented the current paper sizing rule in `docs/API_WORKFLOWS.md`, `docs/TRADING_MODES.md`, `docs/DATA_MODEL.md`, `docs/MODELING_PLAN.md`, and `docs/ROADMAP.md`.
- Updated `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, and `docs/BACKTESTING_SPEC.md` for backtest coverage diagnostics.
- Updated `.env.example`, `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/BACKTESTING_SPEC.md`, `docs/DATA_SOURCES.md`, `docs/LOCAL_DEMO.md`, and `docs/TECHNICAL_DECISIONS.md` for optional credential-gated NOAA CDO observed-outcome resolution.
- Expanded NOAA outcome-resolution documentation with concrete request bodies, environment setup, failure modes, local demo commands, and current station-selection limitations.
- Removed the parse-route demo price fallback so price snapshots come from discovery or explicit refresh, then updated `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, and `docs/LOCAL_DEMO.md`.
- Updated `README.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, `docs/LOCAL_DEMO.md`, and `docs/ROADMAP.md` for market detail workflow status.

### Verified

- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py tests\test_paper_market_runner_cli.py tests\test_api_paper_runner.py`; all 38 focused paper-runner/API/CLI tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 168 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 24 focused backtesting, evidence-report, lifecycle, and market-implied coverage tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 164 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 22 focused backtesting, evidence-report, and lifecycle tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 162 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py tests\test_paper_market_runner_cli.py tests\test_api_paper_runner.py`; all 34 focused rehearsal, runner, API, and CLI tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 161 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_demo.py tests\test_paper_market_runner.py tests\test_migrations.py`; all 20 focused signal snapshot and migration tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 157 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 21 focused backtesting and outcome eligibility tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 157 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py tests\test_paper_market_runner_cli.py tests\test_api_paper_runner.py`; all 30 focused paper-runner portfolio-limit/API/CLI tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 156 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py tests\test_paper_market_runner_cli.py tests\test_api_paper_runner.py`; all 24 focused paper-runner freshness/API/CLI tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 150 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 20 focused backtesting, settlement, batch resolution, and evidence-report tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 146 backend tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\pre_run_smoke.py --help`; the pre-run smoke command help rendered successfully.
- Ran `.\.venv\Scripts\python.exe -m compileall app scripts`; backend app and scripts compiled successfully.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 17 focused backtesting tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py tests\test_api_dashboard.py`; all 21 focused backtesting/dashboard tests passed.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed after adding settlement cost fields.
- Ran `.\.venv\Scripts\pytest.exe`; all 143 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_parser.py tests\test_baseline_model.py tests\test_paper_market_runner.py tests\test_paper_market_runner_cli.py tests\test_api_paper_runner.py tests\test_api_markets.py tests\test_geocoding.py tests\test_backtesting.py`; all 78 focused parser/modeling/runner/API/geocoding/backtesting tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run --max-spread 1 --process-limit 25`; default-off public dry-run reported interval contracts separately while processing precipitation candidates through forecast/model/EV.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run --max-spread 1 --process-limit 25 --allow-interval-contracts`; opt-in public dry-run advanced interval contracts through forecast/model/EV and left only non-precipitation parser skips.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run --max-spread 1`; default process-limit public dry-run prioritized precipitation markets and avoided space-weather parser failures in the first 10 processed markets.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py tests\test_market_parser.py tests\test_baseline_model.py`; all 31 focused parser/modeling/runner tests passed after tightening default-off behavior for stored interval parses.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run --max-spread 1 --process-limit 25`; default-off public dry-run continued to report interval contracts as skipped even after a prior opt-in run had created parsed interval records.
- Ran `.\.venv\Scripts\pytest.exe`; all 142 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_parser.py tests\test_paper_market_runner.py tests\test_api_paper_runner.py`; all 24 focused parser and paper-runner tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run --max-spread 1 --process-limit 25`; public dry-run now reports `parse_failed_interval_contract=8` separately from `parse_failed_not_precipitation=14`.
- Ran `.\.venv\Scripts\pytest.exe`; all 131 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py tests\test_api_paper_runner.py`; all 10 focused paper-runner diagnostics tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_dashboard.py`; all 4 dashboard API tests passed after refining source diagnostic labels.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed after refining source diagnostic labels.
- Ran `.\.venv\Scripts\pytest.exe`; all 127 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_dashboard.py`; all 3 dashboard API tests passed.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed after adding paper-runner dashboard history.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_paper_runner.py tests\test_paper_market_runner.py`; all 8 focused paper-runner tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 126 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_parser.py tests\test_baseline_model.py tests\test_backtesting.py`; all 31 focused parser/model/backtesting tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run`; public dry-run no longer reported `parse_failed` for the sampled one-sided precipitation market and now skips it at the expected fixture-geocoding boundary with `missing_coordinates=1`.
- Ran `.\.venv\Scripts\pytest.exe`; all 126 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py`; all 6 focused paper-runner tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --dry-run`; public dry-run discovered 25 markets and recorded `price_refresh_failed_used_stored_snapshot=10` instead of hard-skipping those refresh failures.
- Ran `.\.venv\Scripts\pytest.exe`; all 122 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py tests\test_api_paper_runner.py tests\test_paper_market_runner_cli.py tests\test_migrations.py`; all 11 focused runner/API/migration tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py tests\test_api_paper_runner.py tests\test_migrations.py`; all 8 focused runner/API/migration tests passed after adding failed-run persistence coverage.
- Ran `.\.venv\Scripts\pytest.exe`; all 121 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 39 focused public market integration tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner_cli.py`; all 4 CLI tests passed.
- Ran `.\.venv\Scripts\python.exe -m py_compile scripts\paper_market_runner.py`; compilation succeeded after adding loop mode.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --help`; CLI help showed the loop-mode flags.
- Ran `.\.venv\Scripts\pytest.exe tests\test_paper_market_runner.py`; all 3 runner tests passed.
- Ran `.\.venv\Scripts\python.exe -m py_compile scripts\paper_market_runner.py app\strategy\paper_market_runner.py`; compilation succeeded.
- Ran `.\.venv\Scripts\python.exe scripts\paper_market_runner.py --help`; CLI help rendered successfully.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_dashboard.py`; all 3 dashboard API tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 36 focused public market-data tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 31 focused public market-data tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_demo.py tests\test_api_dashboard.py`; all 4 focused demo/dashboard tests passed.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed after adding the dashboard action.
- Ran `.\.venv\Scripts\pytest.exe`; all 98 backend tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory`; the deterministic workflow completed through an OPEN paper trade.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed after final docs updates.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_dashboard.py tests\test_backtesting.py`; all 16 focused dashboard/backtesting tests passed.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 96 backend tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory`; the deterministic workflow completed through an OPEN paper trade.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed after the final docs update.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 14 focused backtesting tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_config.py tests\test_health.py`; all 6 focused config and health tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_parser.py tests\test_market_discovery.py tests\test_api_markets.py`; all 38 focused parser/discovery/market API tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 96 backend tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory`; the deterministic workflow completed through an OPEN paper trade using the refreshed `mock-nyc-rain-tomorrow` market.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_dashboard.py`; both dashboard API tests passed.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 88 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 28 focused market tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 88 backend tests passed.
- Ran `npm run build` in `frontend`; the TypeScript and Vite production build passed.
- Ran `npm audit --audit-level=moderate` after updating the Vite toolchain; npm reported 0 vulnerabilities during the install audit.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_dashboard.py`; both dashboard API tests passed after adding the frontend.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_dashboard.py`; both dashboard API tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 86 backend tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory`; the deterministic workflow completed through an OPEN paper trade.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_markets.py`; all 13 market API tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_ev.py`; all 17 focused EV and risk-sizing tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_provenance.py tests\test_api_markets.py tests\test_ev.py`; all 32 focused API/provenance/EV tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 84 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 10 focused backtesting tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 13 focused backtesting tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_markets.py tests\test_api_provenance.py tests\test_ev.py`; all 20 focused API/provenance/EV tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_markets.py`; all 13 market API tests passed.

## 2026-05-08

### Added

- Added structured public market-data errors for Polymarket-style requests, including endpoint, reason, retry attempts, HTTP status code, and retryable flag.
- Added retry handling for public Polymarket-style market-data requests, including rate-limit and transient HTTP status retries.
- Added focused tests for rate-limit retry success, exhausted rate-limit failures, malformed JSON failures, and persisted rate-limit diagnostics on price refresh.
- Added optional Open-Meteo geocoding support behind the existing geocoding adapter.
- Added `OPEN_METEO_GEOCODING_BASE_URL` and `GEOCODING_PROVIDER` settings, with fixture geocoding remaining the default.
- Added focused tests for fixture-first geocoding, Open-Meteo geocoding normalization, empty provider results, and route-level external geocoding enrichment.
- Added a read-only public source price refresh service for Polymarket-sourced markets.
- Added `PolymarketClient.fetch_market` for public Gamma market reads.
- Added fixture-backed tests proving Polymarket price refresh uses a fresh source payload without live network calls.
- Added market-level `source_diagnostics` persistence for public market integration coverage and unsupported price reasons.
- Added Alembic migration `20260508_0002_market_source_diagnostics.py`.
- Added fixture-backed tests for supported, partial, and unsupported source price diagnostics.
- Added captured-style Gamma event fixture coverage for weather markets where the child market question depends on parent event context.
- Added malformed Gamma-style price fixture coverage to verify diagnostics report unparseable price fields even when liquidity and volume parse successfully.
- Added fixture-backed coverage for fresh CLOB token price maps that need stored Gamma market context to resolve YES/NO token IDs.
- Added NOAA/NCEI CDO-style daily `PRCP` observed precipitation normalization for fixture/manual provider payloads with explicit units.
- Added tests for NOAA-style observed outcome creation, missing PRCP units, and mixed PRCP units.

### Changed

- Updated Polymarket price refresh failure diagnostics to persist structured `public_source_error` context alongside `source_refresh_failed`.
- Updated `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, and `docs/DATA_SOURCES.md` for public market-data retry and failure-diagnostic behavior.
- Updated market parsing to call the async geocoding resolver and surface external geocoding provider failures as `502` errors when the provider is enabled.
- Updated `.env.example`, `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_SOURCES.md`, `docs/LOCAL_DEMO.md`, and `docs/TECHNICAL_DECISIONS.md` for optional broad geocoding.
- Updated `POST /markets/{market_id}/price-snapshots/refresh` so Polymarket markets fetch a fresh public payload before persisting a new immutable price snapshot, while manual or fixture-backed markets keep stored-payload refresh support.
- Updated public source refresh failures to persist diagnostic context with `source_refresh_failed`.
- Updated `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, and `docs/DATA_SOURCES.md` for fresh public price refresh behavior.
- Expanded `.gitignore` to exclude local secrets, virtual environments, Python/test caches, coverage output, build artifacts, local databases, logs, and editor state while keeping `.env.example` trackable.
- Updated market discovery and price refresh flows to record diagnostics for metadata, condition IDs, binary prices, top-of-book data, liquidity, volume, status, resolution metadata, and unsupported price payloads.
- Updated `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, and `docs/DATA_SOURCES.md` for the new source diagnostics behavior.
- Updated Polymarket-style discovery to match weather keywords against child market fields plus parent event title, category, description, and tags.
- Updated price normalization so current Gamma `outcomePrices` take precedence over `lastTradePrice` when both are present.
- Updated source diagnostics to report `price_fields_not_parseable` when recognized price fields fail parsing but ancillary fields still produce a partial snapshot.
- Updated Polymarket price refresh to merge stored market context into fresh public price payloads when the fresh payload omits outcome and token-id metadata.
- Updated `docs/ROADMAP.md` and `docs/DATA_SOURCES.md` for the new real-market fixture coverage.
- Updated `docs/ROADMAP.md`, `docs/DATA_SOURCES.md`, and `docs/BACKTESTING_SPEC.md` for fixture/manual NOAA-style observed outcome normalization.
- Updated `docs/ROADMAP.md` to explicitly track a future credential-gated NOAA/NWS observed-weather client while keeping local demos and tests credential-free.
- Polished `README.md`, `docs/LOCAL_DEMO.md`, `docs/DEMO_PLAN.md`, and `docs/PORTFOLIO_POSITIONING.md` with an architecture overview, expected scripted-demo output, representative seed backtest output, and clearer implemented-versus-planned outcome-provider boundaries.
- Updated `docs/ROADMAP.md` to mark Phase 7 portfolio polish as partially implemented.

### Verified

- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 24 focused market tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 67 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_geocoding.py tests\test_api_markets.py`; all 15 focused geocoding and market API tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 62 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_markets.py tests\test_market_discovery.py`; all 17 focused market tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 57 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_markets.py tests\test_market_discovery.py`; all 20 focused market tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 63 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py tests\test_migrations.py`; all 15 focused market and migration tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 50 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 16 focused market tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 52 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 9 focused backtesting tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 55 backend tests passed.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory`; the deterministic workflow completed through an OPEN paper trade.
- Ran `.\.venv\Scripts\pytest.exe`; all 55 backend tests passed after documentation polish.

## 2026-05-07

### Added

- Added Open-Meteo archive observed-weather outcome resolution for parsed precipitation markets.
- Added `POST /backtests/resolved-outcomes/resolve-weather` to persist source-attributed resolved outcomes from observed precipitation data.
- Added tests for observed precipitation outcome normalization, unit validation, threshold comparison, and route-level persistence without live network calls.
- Added resolved outcome create/list API endpoints under `/backtests/resolved-outcomes`.
- Added a backtest runner that replays stored predictions joined to resolved outcomes by model version and resolved-at date window.
- Added backtest win rate, calibration buckets, and sample-size notes.
- Added backtest EV recommendation counts, paper-trade counts, settlement PnL, paper ROI, and max-drawdown summaries.
- Added reusable calibration bucket calculation in `backend/app/modeling/calibration.py`.
- Added deterministic seed-fixture replay support through `seed_fixtures` on `POST /backtests/run`.
- Added seed replay fixture data under `backend/app/backtesting/fixtures/seed_replay.json`, including EV recommendation and paper-trade records.
- Added focused calibration tests.
- Added backtesting tests for resolved outcome creation, persisted prediction/outcome replay, and seed-fixture replay.
- Added `backend/scripts/demo_workflow.py`, a scripted end-to-end FastAPI route workflow for mock discovery, parsing, deterministic forecast snapshot creation, prediction, EV evaluation, and paper-trade creation.
- Added `--sqlite-memory` smoke-demo support and `--use-open-meteo` live forecast-provider opt-in for the demo workflow script.
- Added fixture-backed market price payloads for Gamma-style outcome prices, a CLOB orderbook, and CLOB token BUY/SELL price maps.
- Added tests for CLOB token price-map normalization and refresh-route persistence.
- Added API provenance tests proving prediction runs record the exact latest parsed market and forecast snapshot, and strategy evaluation records the exact latest price snapshot.
- Added `prediction_id` and `price_snapshot_id` to strategy opportunity responses for input traceability.
- Added Open-Meteo forecast fixture files for mixed values, missing values, and inch-unit payloads.
- Added fixture-backed forecast normalization tests for numeric strings, malformed values, missing values, unit preservation, millimeter-to-inch conversion, temperature summaries, and raw payload preservation.
- Added `backend/app/weather/geocoding.py` with a deterministic fixture geocoder for New York City, NYC, New York, and Chicago.
- Added route-level location resolution during market parsing so parsed markets receive coordinates through a service rather than parser hardcoding.
- Added tests for the fixture geocoder, route-level geocoding enrichment, and unknown-location behavior.
- Added expanded precipitation parser coverage for `over`, `above`, `greater than`, `no less than`, `or more`, `precipitation`, and "rain in location" wording.
- Added clearer parser failure reasons for non-precipitation questions, missing numeric thresholds, unsupported units, and unsupported precipitation wording.
- Added focused parser tests for newly supported wording and failure reasons.
- Added `POST /markets/{market_id}/price-snapshots/refresh` to persist a new price snapshot from a market's stored raw source payload.
- Added price normalization support for token outcome lists, last-trade-style fields, and orderbook-like bid/ask payloads.
- Added focused API tests for price snapshot refresh success and unsupported payload failures.
- Added source-aware market price snapshot normalization for mock and common Polymarket-style discovery payload fields.
- Added discovery-time persistence of `market_price_snapshots` when source price data is available.
- Added `price_snapshots_created` to the market discovery response.
- Added focused tests for price snapshot normalization and mock discovery price snapshot persistence.
- Added this changelog to track changes made after each implementation prompt.
- Added Alembic as the database migration tool for the backend.
- Added Alembic configuration under `backend/alembic.ini`.
- Added Alembic environment wiring in `backend/migrations/env.py` that loads `DATABASE_URL` through the application settings.
- Added an initial migration, `backend/migrations/versions/20260507_0001_initial_schema.py`, for the current SQLAlchemy ORM schema.
- Added `backend/tests/test_migrations.py` to verify `alembic upgrade head` creates the expected schema tables on a fresh database.

### Changed

- Updated `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/BACKTESTING_SPEC.md`, and `docs/DATA_SOURCES.md` for the initial external observed-outcome resolver.
- Replaced the placeholder `/backtests/run` response with initial replay output containing prediction count, resolved outcome count, Brier score, log loss, status, and source.
- Expanded `/backtests/run` output with win rate, calibration buckets, and a sample-size note.
- Expanded `/backtests/run` output with EV recommendation and paper-trade replay summaries.
- Updated `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/BACKTESTING_SPEC.md`, and `docs/MODELING_PLAN.md` for the initial resolved-outcome, replay, calibration, and paper-trade summary behavior.
- Polished `README.md`, `docs/LOCAL_DEMO.md`, `docs/DEMO_PLAN.md`, and `docs/PORTFOLIO_POSITIONING.md` so the local demo and portfolio narrative reflect the implemented backtest replay.
- Added demo documentation notes to verify tests pass with PostgreSQL running through Docker Compose before portfolio review.
- Updated `README.md`, `docs/LOCAL_DEMO.md`, `docs/DEMO_PLAN.md`, and `docs/ROADMAP.md` for the scripted demo workflow.
- Hardened market price normalization for `clobTokenIds` plus token `BUY`/`SELL` price maps, mapping BUY to best ask and SELL to best bid.
- Added direct `midpoint`/`mid` support for YES price normalization.
- Updated `docs/API_WORKFLOWS.md`, `docs/DATA_SOURCES.md`, and `docs/ROADMAP.md` for the expanded fixture-backed public price normalization behavior.
- Updated strategy evaluation responses to expose the prediction's `parsed_market_id` and `forecast_snapshot_id` alongside the recommendation's `prediction_id` and `price_snapshot_id`.
- Updated `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, and `docs/ROADMAP.md` for prediction and EV provenance behavior.
- Updated `docs/ROADMAP.md` to summarize the completed Docker/Alembic verification, discovery price snapshots, price refresh endpoint, parser expansion, fixture geocoder, and forecast normalization work, and reordered near-term priorities around the remaining provenance and demo gaps.
- Hardened `backend/app/weather/forecast_service.py` normalization to ignore booleans, parse numeric strings, tolerate malformed lists, normalize precipitation units, and preserve raw provider payloads.
- Updated `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, `docs/ROADMAP.md`, `docs/DEMO_PLAN.md`, and `docs/TECHNICAL_DECISIONS.md` for fixture-backed forecast normalization behavior.
- Removed hardcoded coordinate lookup from the precipitation parser; parser output now contains extracted location text and the parse route handles coordinate enrichment.
- Updated `README.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, `docs/ROADMAP.md`, `docs/DEMO_PLAN.md`, and `docs/TECHNICAL_DECISIONS.md` for fixture-backed geocoding behavior.
- Updated `docs/API_WORKFLOWS.md`, `docs/ROADMAP.md`, `docs/DEMO_PLAN.md`, and `docs/TECHNICAL_DECISIONS.md` for the expanded parser behavior.
- Cleaned up `docs/ROADMAP.md` near-term ordering so completed parser work is no longer listed as the immediate next item.
- Updated `README.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, and `docs/ROADMAP.md` for the price snapshot refresh workflow.
- Updated market parsing to keep its mock price creation only as a demo fallback for manually seeded markets without source snapshots.
- Updated `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, and `docs/ROADMAP.md` to describe discovery-time price snapshot behavior.
- Documented local Docker Compose setup, status, logs, stop, restart, and teardown commands in `README.md`.
- Updated `docs/LOCAL_DEMO.md` and `docs/DEMO_PLAN.md` with Docker status checks and the migration step needed before starting the API.
- Updated `docs/ROADMAP.md` to mark Docker/PostgreSQL migration verification as complete.
- Updated `AGENTS.md` to require documenting each Codex-assisted implementation change in `CHANGELOG.md` after each prompt.
- Updated `AGENTS.md` to list Alembic as an active dependency instead of a planned migration tool.
- Updated `backend/requirements.txt` to include `alembic==1.14.0`.
- Updated `README.md` with migration setup and revision-generation commands.
- Updated `docs/DATA_MODEL.md` to describe Alembic-backed schema management.
- Updated `docs/LOCAL_DEMO.md` so local startup runs `alembic upgrade head` before the API.
- Updated `docs/ROADMAP.md` to mark Phase 1 persistence work as implemented and later verified through Docker/PostgreSQL.

### Verified

- Ran `.\.venv\Scripts\pytest.exe tests\test_backtesting.py`; all 6 focused backtesting and outcome resolver tests passed.
- Ran `.\.venv\Scripts\python.exe -m py_compile app\backtesting\outcome_resolver.py app\api\routes_backtests.py app\weather\open_meteo_client.py`; compilation succeeded.
- Ran `.\.venv\Scripts\pytest.exe`; all 49 backend tests passed.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_backtesting.py`; all 3 focused backtesting tests passed.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_calibration.py tests\test_backtesting.py`; all 5 focused calibration/backtesting tests passed.
- Ran `.\.venv\Scripts\python.exe -m pytest tests\test_backtesting.py`; all 3 focused backtesting tests passed after adding paper-trade summaries.
- Ran `.\.venv\Scripts\python.exe -m pytest`; all 44 backend tests passed.
- Ran `.\.venv\Scripts\python.exe -m pytest`; all 46 backend tests passed.
- Ran `.\.venv\Scripts\python.exe -m pytest`; all 46 backend tests passed after adding paper-trade summaries.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory`; the deterministic workflow completed through an OPEN paper trade.
- Ran `.\.venv\Scripts\python.exe -m pytest`; all 46 backend tests passed after documentation polish.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py --help`; command help rendered successfully.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py --sqlite-memory`; the deterministic workflow completed through an OPEN paper trade.
- Ran `.\.venv\Scripts\python.exe scripts\demo_workflow.py`; it failed closed with a concise database setup message because Docker/PostgreSQL was not running in this environment.
- Ran `.\.venv\Scripts\python.exe -m py_compile scripts\demo_workflow.py`; the demo script compiled successfully.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 13 focused market tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 41 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_api_provenance.py tests\test_api_markets.py tests\test_ev.py`; all 14 focused tests passed.
- Ran `.\.venv\Scripts\pytest.exe`; all 39 backend tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_forecast_service.py`; all 4 forecast normalization tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_geocoding.py tests\test_market_parser.py tests\test_api_markets.py`; all 16 focused tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_parser.py`; all 8 parser tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 10 focused market tests passed.
- Ran `.\.venv\Scripts\pytest.exe tests\test_market_discovery.py tests\test_api_markets.py`; all 6 focused market tests passed.
- Started PostgreSQL 16 with `docker compose up -d`; `docker compose ps` showed `weatheredge-postgres` running on `localhost:5432`.
- Ran `.\.venv\Scripts\alembic.exe upgrade head` against the local Docker PostgreSQL database successfully.
- Ran the backend test suite with `.\.venv\Scripts\pytest`; all 20 tests passed.
- Verified Alembic sees the initial migration with `.\.venv\Scripts\alembic history`.

### Limitations

- Docker Desktop was not running or accessible in this environment, so the scripted demo was verified with `--sqlite-memory` instead of local PostgreSQL.
- Docker commands may require Docker Desktop to be running and the current Windows user to have Docker engine access.

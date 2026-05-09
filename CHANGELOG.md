# Changelog

All notable Codex-assisted changes to WeatherEdge AI are documented here after each implementation prompt.

## 2026-05-09

### Added

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

# Changelog

All notable Codex-assisted changes to WeatherEdge AI are documented here after each implementation prompt.

## 2026-05-09

### Added

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

- Updated market detail API docs to describe the full latest paper-trading inspection chain.
- Updated strategy evaluation to use the shared paper risk-sizing helper and include sizing rationale in actionable recommendation reasons.
- Documented the current paper sizing rule in `docs/API_WORKFLOWS.md`, `docs/TRADING_MODES.md`, `docs/DATA_MODEL.md`, `docs/MODELING_PLAN.md`, and `docs/ROADMAP.md`.
- Updated `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, and `docs/BACKTESTING_SPEC.md` for backtest coverage diagnostics.
- Updated `.env.example`, `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/BACKTESTING_SPEC.md`, `docs/DATA_SOURCES.md`, `docs/LOCAL_DEMO.md`, and `docs/TECHNICAL_DECISIONS.md` for optional credential-gated NOAA CDO observed-outcome resolution.
- Expanded NOAA outcome-resolution documentation with concrete request bodies, environment setup, failure modes, local demo commands, and current station-selection limitations.
- Removed the parse-route demo price fallback so price snapshots come from discovery or explicit refresh, then updated `README.md`, `docs/ROADMAP.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, and `docs/LOCAL_DEMO.md`.
- Updated `README.md`, `docs/API_WORKFLOWS.md`, `docs/DATA_MODEL.md`, `docs/LOCAL_DEMO.md`, and `docs/ROADMAP.md` for market detail workflow status.

### Verified

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

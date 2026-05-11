# Roadmap

## Goal

Build WeatherEdge AI into a portfolio-grade backend project that demonstrates production-minded API design, data modeling, external API integration, probability modeling, strategy evaluation, and responsible AI/ML engineering.

The project should tell a clear hiring story: a market is discovered from a real or mock source, parsed into a weather target, connected to forecast data, scored by a documented probability model, compared against market prices, evaluated through paper trading and backtesting, and eventually routed through safety-gated live execution.

Paper trading must be implemented first and remain the default mode for local development, tests, demos, and validation. Live trading may be added later in this backend only after explicit safety controls exist, including live-mode configuration, credential isolation, position limits, kill-switch behavior, audit logging, and tests that prove paper mode cannot place real orders.

## Portfolio Principles

- Prioritize visible hiring signal over feature volume.
- Make every phase easier to demo, explain, test, and extend.
- Prefer end-to-end workflow credibility over isolated features.
- Preserve raw source payloads and immutable snapshots for reproducibility.
- Keep model assumptions explicit and testable.
- Use real market and weather integrations where they improve the research and trading-readiness story.
- Treat live execution as safety-gated functionality, not a shortcut around paper-trading validation.

## Current Project Status

The project is currently around Phase 5 in feature shape. Phase 1 persistence is implemented and verified with Alembic, Docker Compose, and local PostgreSQL. Phases 2-4 have a working end-to-end paper-trading research flow. Phase 5 now has resolved-outcome replay with one selected outcome per market, calibration buckets, sample-size reporting, coverage diagnostics, paper-trade replay summaries, and Open-Meteo archive observed-weather outcome resolution, but still needs broader provider coverage and portfolio polish before it is portfolio-ready.

Implemented:

- FastAPI backend structure.
- SQLAlchemy ORM models for markets, parsed markets, price snapshots, forecast snapshots, predictions, EV recommendations, resolved outcomes, paper trades, and paper runner runs.
- Pydantic schemas.
- Market, weather, prediction, strategy, paper-trade, and backtest route modules.
- Mock market discovery and a Polymarket-style public discovery path.
- Keyword-based public discovery through Gamma `public-search`, with event deduplication, child-market expansion, inactive/closed child filtering, and active-event fallback.
- Idempotent persistence for discovered market records.
- Discovery-time market price snapshot persistence.
- `POST /markets/{market_id}/price-snapshots/refresh` for read-only price snapshot refresh from fresh public source payloads on Polymarket markets, with stored-payload support for manual or fixture-backed markets.
- Source-aware price normalization for mock, common Polymarket-style market fields, token outcome fields, CLOB token price maps, and orderbook-like bid/ask payloads.
- Market-level source diagnostics for supported, partial, and unsupported public market payloads.
- Public market-data request retry handling with persisted diagnostics for rate limits, HTTP failures, malformed JSON, malformed payloads, and retry attempts during price refresh.
- Public paper runner can optionally fall back to the latest stored discovery-time binary price snapshot when a read-only public price refresh fails, with `stale_supported` diagnostics preserving the provider error and fallback snapshot ID only when stale fallback is explicitly enabled.
- Captured-style fixture coverage for nested CLOB orderbook containers, nested Gamma-style stats payloads, wrapped Gamma-style market payloads, token `lastPrice` rows, and unsupported partial-price shapes, including specific diagnostics when liquidity/volume are present without binary YES/NO prices.
- Parse route no longer creates demo fallback price snapshots; price provenance now comes from discovery or explicit refresh.
- Event-level weather context matching for Polymarket-style discovery when child market questions rely on parent event metadata.
- Fixture-backed diagnostics for malformed Gamma-style price fields that still expose usable liquidity or volume fields.
- Expanded rule-based precipitation parser coverage for common threshold wording, including less-than thresholds and millimeter units.
- Parser failure reasons for non-precipitation questions, missing thresholds, unsupported units, and unsupported precipitation wording.
- Deterministic fixture geocoder for local demos and tests, including current public precipitation demo cities.
- Optional Open-Meteo geocoding provider behind the geocoding adapter.
- Explicit `TRADING_MODE` and `LIVE_TRADING_ENABLED` settings, with paper mode as the default and live execution disallowed unless both live settings are enabled.
- Open-Meteo forecast client support.
- Forecast snapshot persistence.
- Fixture-backed forecast normalization for mixed values, missing values, unit conversion, temperature summaries, and raw payload preservation.
- Baseline precipitation probability model for one-sided precipitation thresholds, including greater-than and less-than style markets, plus opt-in interval precipitation contracts for paper-runner research.
- Stored prediction outputs with model version, feature payload, parsed-market provenance, and forecast-snapshot provenance.
- Expected-value helpers and stored EV recommendations with price-snapshot provenance.
- Market detail workflow status showing completed pipeline steps and the next recommended backend action.
- Market detail reads expose the latest forecast snapshot and latest paper trade alongside parsed market, price snapshot, prediction, EV recommendation, and workflow status.
- Read-only dashboard summary endpoint for recent market workflow rows, compact source diagnostics, compact latest signal values, backtest/calibration metrics, paper-buy opportunities, and open paper trades.
- Paper-only demo workflow endpoint, `POST /demo/paper-workflow`, for one-click mock discovery, parsing, fixture forecast creation, prediction, EV evaluation, and simulated paper-trade creation.
- One-shot public-market paper runner script with discovery, price refresh, eligibility skips, forecast/model/EV evaluation, max-trade caps, duplicate open-side checks, and simulated paper-trade creation only.
- Public paper-runner candidate prioritization so V1 precipitation markets are processed before broad weather false positives such as space-weather event counts.
- Persisted `paper_runner_runs` records and API endpoints for one-shot public paper-run execution and run-history inspection.
- Aggregated `GET /paper-runner/diagnostics` reporting recent public paper-run counts, categorized skip reasons, market source price-status counts, unsupported public price reasons, and recent workflow/provider errors.
- Paper-trade endpoints.
- Scripted end-to-end demo workflow for mock discovery, parsing, deterministic forecast snapshot creation, prediction, EV evaluation, and paper-trade creation.
- README and local demo docs now include architecture flow, expected smoke-demo output, representative seed backtest output, and current observed-outcome boundaries.
- Resolved outcome create/list endpoints.
- Open-Meteo archive observed precipitation resolver that creates source-attributed resolved outcomes from the latest parsed market.
- NOAA/NCEI CDO-style daily `PRCP` observed precipitation normalization for fixture/manual provider payloads with explicit units.
- Credential-gated NOAA/NCEI CDO daily precipitation client behind the observed-outcome resolver, with mocked tests and Open-Meteo remaining the default demo path.
- Minimal backtest replay over persisted resolved predictions, selecting one latest resolved outcome per market inside the requested evaluation window.
- Deterministic seed-fixture backtest replay for local demos and tests.
- Backtest win rate, Brier score, log loss, calibration buckets, sample-size notes, sample-size gates, and baseline comparisons.
- Backtest EV recommendation counts and paper-trade PnL, ROI, and max-drawdown summaries.
- Backtest coverage diagnostics for missing outcomes, unmatched outcomes, and model-version exclusions.
- Outcome-based paper-trade settlement from resolved outcomes.
- Batch observed-weather outcome resolution for eligible completed parsed markets.
- Compact multi-day evidence reporting through `GET /evaluation/evidence-report`.
- Pre-run smoke checks for database, schema, paper-mode safety, and seed-fixture replay.
- Passing backend test suite.

Partially implemented:

- Real public market price coverage has fixture coverage and persisted diagnostics for several documented shapes, including event-wrapped weather markets, malformed Gamma-style price fields, nested CLOB orderbooks, nested stats-only payloads, wrapped Gamma-style market payloads, token `lastPrice` rows, non-binary outcomes, outcome/price length mismatches, missing token context, and empty orderbooks, but should keep expanding as unsupported source response variations are captured.
- Polymarket price refresh now calls the public source client for fresh Gamma market payloads, can optionally enrich them with CLOB market metadata, and can combine fresh CLOB token price maps with stored Gamma market context when the fresh response omits outcome and token-id metadata, but broader real response capture and endpoint-shape hardening should continue as unsupported variations are found.
- A public-market paper runner exists for manual validation and bounded overnight loops, with durable run history now persisted. Alerting and production-grade retry scheduling remain future work.
- Prediction and EV routes use stored inputs and expose the main provenance IDs.
- Market detail reads expose computed workflow status so reviewers can see whether price refresh, parsing, forecasting, prediction, or strategy evaluation is next.
- Market detail reads now expose the full latest paper-trading inspection chain, including forecast snapshot and paper trade records.
- A first frontend contract exists through `GET /dashboard/summary`, keeping the dashboard read-only and backed by existing paper-trading records with compact source diagnostics, latest parsed target, forecast, model, price, EV, paper-trade status, backtest metrics, and calibration values.
- Location resolution has a deterministic fixture geocoder by default, plus an opt-in Open-Meteo geocoding provider for broader manual coverage.
- Backtesting has an initial replay path for persisted predictions evaluated against one selected outcome per market, plus seed-fixture support, calibration buckets, sample-size reporting, sample-size gates, baseline comparisons, coverage diagnostics, and paper-trade result summaries.
- Multi-day paper-run evaluation now has outcome batch resolution, paper-trade settlement, a compact evidence report, and a pre-run smoke command.

Known gaps:

- Deterministic fixture geocoding remains the default for local demos and tests. Open-Meteo geocoding is available as an opt-in provider, but captured edge-case coverage should continue expanding.
- Parser failure detail exists for common unsupported cases, and one-sided inch/mm threshold coverage has expanded from real public dry-run misses. Interval contracts such as `between 2 and 3 inches` are supported only behind an explicit experimental paper-runner/API/CLI toggle; the baseline is simple and should not be treated as proven performance.
- Captured-style fixture coverage and source diagnostics exist for public market price payload variations, including nested orderbook payloads, nested stats-only payloads, wrapped market payloads, token `lastPrice` rows, non-binary outcomes, outcome/price length mismatches, missing token context, empty orderbooks, and split fresh-price/stored-market-context refreshes. Public request retries and failure diagnostics are implemented, but more real response captures should be added as integration gaps are found.
- Open-Meteo archive outcome resolution exists for parsed precipitation markets with coordinates and target dates, and NOAA/NCEI CDO-style daily `PRCP` payload normalization plus an optional credential-gated NOAA CDO client exist behind the resolver interface.
- Frontend UI has a dashboard with inline latest-signal inspection, compact source diagnostics, compact backtest/calibration context, paper-trade inspection, recent public paper-runner history, a safe `Run Paper Demo` action, and a public `Run Public Dry Run` action that does not create trades. Broader workflow controls remain a planned follow-up.
- Public-market paper trading is available as a guarded script and one-shot API. It runs once by default, can run bounded overnight loops with explicit `--interval-minutes` plus `--max-hours` or `--max-runs`, stores durable run history, exposes aggregated diagnostics for skipped markets and unsupported public price payloads, and only continues from stored discovery-time prices when refresh fails if stale fallback is explicitly enabled. It is not yet a daemon with alerting.

## Phase 1: Persistence Foundation

Status: implemented and verified against local Docker PostgreSQL.

Objective: make the database layer credible and maintainable before adding more workflow complexity.

Work:

- Add Alembic. Done.
- Generate an initial migration for the current ORM models. Done.
- Ensure migrations use the project settings/database URL cleanly. Done.
- Verify a fresh local Postgres database can be created from migrations through Docker Compose. Done.
- Add migration instructions to README or docs. Done.
- Add repository-level tests where they prove important persistence behavior. Initial Alembic upgrade smoke test added.

Done when:

- `alembic upgrade head` creates a fresh working schema.
- Tests still pass.
- A reviewer can understand how schema changes are managed.
- The app no longer relies on implicit table creation as the main schema-management story.

Portfolio value:

- Shows production-minded backend practice.
- Makes future schema work defensible.
- Gives reviewers confidence that data modeling is intentional, not incidental.

## Phase 2: Market Ingestion And Parsing

Status: partially done.

Objective: turn market discovery into a repeatable pipeline that can ingest real public market data while preserving a reliable mock path for demos and tests.

Already present:

- `POST /markets/discover`.
- Mock discovery path.
- Polymarket-style public discovery path using Gamma `public-search` first, with active-event fallback.
- Idempotent market persistence by source and source market ID.
- Raw market payload storage.
- Basic precipitation market parser with coverage for common threshold wording.
- Discovery-time price snapshots and read-only snapshot refresh from fresh public Polymarket payloads, with stored-payload refresh retained for manual and fixture-backed markets.
- Price normalization for mock, common Polymarket-style market fields, token outcome fields, CLOB token price maps, orderbook-like bid/ask fields, spread, liquidity, volume, and timestamps.
- Source diagnostics for market metadata, condition IDs, binary prices, top-of-book data, liquidity, volume, status, resolution metadata, unsupported price reasons, and public source refresh failures.
- Parent event title, category, description, and tag context are considered during public market discovery so weather events are not missed when child market questions omit weather keywords.
- Parser failure reasons and tests for supported and unsupported market formats.

Remaining work:

- Continue adding captured real market fixture payloads for unsupported public price response variations and verify the stored diagnostics stay useful. Event-wrapped weather, malformed price-field, nested orderbook, nested stats-only, wrapped market, token `lastPrice`, non-binary outcome, outcome/price mismatch, missing-token-context, and empty-orderbook fixtures are covered.
- Continue hardening market price snapshots during discovery and through the dedicated refresh endpoint as new fixtures reveal gaps.
- Continue expanding public-source failure fixtures beyond the initial rate-limit, malformed JSON, and malformed payload coverage.
- Remove or further isolate the parse-route demo fallback that creates a mock price snapshot for manually seeded markets. Done; parsing no longer creates price snapshots.
- Continue expanding parsing coverage as unsupported real market questions are captured. Less-than thresholds and millimeter units are now covered; interval/range markets remain future work.
- Continue refining parser failure reasons from observed failures.

Done when:

- `POST /markets/discover` can ingest and persist markets idempotently.
- Real or source-provided price data can be persisted into `market_price_snapshots`. Initial normalization is implemented for mock, common Polymarket-style market fields, token outcome fields, CLOB token price maps, orderbook-like bid/ask fields, spread, liquidity, volume, and timestamps.
- The same discovery or refresh call does not create duplicate markets.
- Price snapshots preserve raw source payloads.
- Several common precipitation question formats are covered by tests. Initial expanded coverage is implemented.

Portfolio value:

- Demonstrates external API integration and idempotent ingestion.
- Shows real-market-data readiness before live trading is enabled.
- Makes the downstream EV workflow credible because prices come from stored source snapshots.

## Phase 3: Location Resolution And Forecast Snapshots

Status: partially done.

Objective: make weather data usable beyond hardcoded demo cities.

Already present:

- Open-Meteo forecast client.
- Forecast snapshot model.
- Forecast snapshot persistence route.
- Basic forecast normalization and unit conversion.
- Fixture-backed tests for Open-Meteo normalization edge cases.
- Deterministic fixture geocoder for New York City, NYC, New York, and Chicago.
- Parse route coordinate enrichment through the fixture geocoder.
- Optional Open-Meteo geocoding client and resolver path for broader manual location coverage.

Remaining work:

- Expand deterministic fixture coverage where useful for demos and tests.
- Capture more external geocoding edge cases with mocked or fixture-backed provider payloads.
- Continue hardening Open-Meteo normalization as captured provider payload variations are added.
- Store and test forecast issue/retrieval time and target window behavior more deeply.
- Add more fixture-based tests for forecast normalization as new edge cases are found.

Done when:

- Parsed markets can receive coordinates through a service rather than parser hardcoding. Fixture-backed resolution is default, and optional Open-Meteo geocoding is implemented for broader manual coverage.
- Forecast snapshots are persisted and queryable.
- Forecast normalization has meaningful fixture coverage. Initial edge-case fixtures are implemented.
- Forecast logic can be tested without network access.

Portfolio value:

- Shows clean adapter boundaries around external services.
- Makes the project feel extensible to new locations and weather providers.
- Strengthens reproducibility by preserving forecast snapshots used by predictions.

## Phase 4: Baseline Modeling And EV Pipeline

Status: partially done.

Objective: produce defensible predictions and paper-trading recommendations from stored data.

Already present:

- Baseline precipitation model.
- Stored predictions with model version, feature payload, parsed-market provenance, and forecast-snapshot provenance.
- EV calculation helpers.
- Stored EV recommendations with prediction and price-snapshot provenance.
- Paper-trade creation and closing routes.

Remaining work:

- Continue improving route responses for demo readability where the scripted workflow reveals gaps.
- Add simple risk sizing documentation and tests. Done for the current capped paper-mode sizing rule.
- Add a single scripted workflow that runs discovery, parsing, forecast, prediction, EV evaluation, and paper-trade creation. Done for the deterministic local route workflow.
- Add documentation explaining baseline model assumptions and limitations.

Done when:

- A single market can flow from discovery to parsed target to forecast to prediction to EV recommendation to paper trade.
- Each stored output links back to the input snapshot used to create it.
- Model behavior is documented and tested.
- The route responses support a clear portfolio demo.

Portfolio value:

- Shows the core product loop.
- Demonstrates probability modeling without pretending the baseline model is more advanced than it is.
- Connects backend data provenance directly to strategy evaluation.

## Phase 5: Backtesting And Calibration

Status: partially implemented.

Objective: show ML judgment and research discipline, not just API plumbing.

Work:

- Add a workflow for resolved outcome records. Initial API create/list endpoints and Open-Meteo archive observed-weather resolution are implemented.
- Implement a historical replay runner for stored markets, forecasts, predictions, and outcomes. Initial prediction/outcome replay is implemented and selects one latest resolved outcome per market inside the evaluation window.
- Compute Brier score and log loss. Initial report fields are implemented.
- Add win rate, prediction count, and simple paper-trading result summaries. Initial win rate, prediction count, EV recommendation count, gross paper PnL, fee and slippage costs, net paper PnL, paper ROI, and max drawdown are implemented.
- Add calibration bucket reporting. Initial calibration buckets are implemented.
- Add coverage diagnostics for skipped or unevaluated records. Initial missing-outcome, unmatched-outcome, and model-version exclusion diagnostics are implemented.
- Create seed fixtures that make backtesting demonstrable without waiting for real historical accumulation. Initial seed replay fixture is implemented.
- Add tests for metric calculations and at least one replay scenario. Initial resolved-outcome, replay, and paper settlement cost-assumption tests are implemented.
- Add external observed-outcome integration. Initial Open-Meteo archive precipitation resolution is implemented with fixture/mocked tests.
- Add broader provider normalization for observed outcomes. Initial NOAA/NCEI CDO-style daily `PRCP` fixture/manual payload normalization is implemented.
- Add a credential-gated NOAA/NWS observed-weather client behind the resolver interface, with mocked tests and clear provider-error diagnostics. Initial NOAA/NCEI CDO daily precipitation client is implemented and remains optional. Do not require NOAA credentials for local demos or the default test path.

Done when:

- Backtests operate on persisted historical-like records or seed fixtures.
- Reports include prediction count, win rate, Brier score, log loss, calibration summary, and coverage diagnostics.
- The backtest output is suitable for a portfolio demo.
- Tests cover metrics and replay behavior.

Portfolio value:

- Separates real ML/research judgment from API plumbing.
- Gives a reviewer evidence that the strategy can be evaluated, not just executed in a demo.
- Creates the evidence base needed before enabling live trading.

Evidence-readiness follow-ups:

- Add rolling or walk-forward backtests so evaluation is not tied to one static split.
- Compare the baseline against simple controls such as market-implied probability and always-50% probability. Done for persisted replay rows with linked market prices.
- Add fee and slippage assumptions to paper-trade settlement summaries so ROI is less naive. Done for backtest paper settlement with zero-cost defaults and explicit gross/cost/net fields.
- Add explicit sample-size gates and stronger sample-size notes in API and dashboard outputs. Initial backtest and evidence-report gates are implemented.
- Add a compact evidence report that exposes counts, filters, unresolved records, and calibration context in one place. Initial `GET /evaluation/evidence-report` is implemented.
- Add paper-trade auto-settlement or closing support when resolved outcomes become available. Initial outcome-based paper settlement is implemented.
- Add outcome-resolution tooling that can generate more evaluated records from archived or fixture-backed weather windows. Initial observed-weather batch resolution is implemented.

Paper-trading hardening priorities before full multi-day runs:

- Add price and forecast freshness guards so paper trades are not opened from stale market or weather inputs.
- Add paper-run rehearsal reporting that estimates eligible markets, skip reasons, provider success rates, actionable recommendations, and expected trade count without creating trades. Initial no-trade rehearsal mode reports actionable recommendations and expected paper trades after normal limits.
- Make duplicate-trade policy explicit with configurable market/side cooldowns and clear skip reasons after trades resolve.
- Add paper portfolio limits for max open trades, simulated notional exposure, per-market exposure, and per-location exposure. Initial conservative paper-runner limits are implemented.
- Add reviewer-friendly paper trade signal snapshots showing parsed target, forecast value, model probability, market price, edge, liquidity, spread, recommendation reason, and runner config. Implemented as `paper_trades.signal_snapshot_json`.
- Add market-implied baseline coverage diagnostics so evidence reports show how much evaluated data can be compared against market prices. Implemented in the evidence report.
- Add outcome eligibility preview for markets ready to resolve, not ready, missing target data, missing coordinates, or already resolved. Initial read-only preview endpoint is implemented.
- Add paper trade lifecycle counts for recommended-but-not-traded, open, resolved, manually closed, and unresolved-past-target-window states. Implemented in the evidence report.
- Add optional simulated entry slippage/fill modeling for paper trades while keeping raw quoted prices inspectable. Implemented with zero default and quoted/fill/slippage details in `signal_snapshot_json`.

## Phase 6: Real Market Research Integration

Status: partially implemented.

Objective: make WeatherEdge AI useful against real public market data while keeping paper trading as the default execution mode.

Work:

- Improve the Polymarket-style public market adapter around real response shapes.
- Use search-oriented public discovery for keyword-based market ingestion. Done with Gamma `public-search`, event deduplication, child-market expansion, inactive/closed filtering, and active-event fallback.
- Expand explicit source capability handling for markets, prices, liquidity, volume, status, and resolution metadata. Initial persisted diagnostics are implemented.
- Add source refresh endpoints or jobs for market metadata and price snapshots. Initial read-only price refresh from fresh public Polymarket-style Gamma payloads is implemented, including optional CLOB metadata enrichment and stored market-context merging for token-only price responses.
- Store provider errors and unsupported-market reasons in a debuggable way. Initial unsupported price reasons are persisted on markets.
- Add rate-limit and retry behavior appropriate for public data access. Initial client retry handling and route-level persisted diagnostics are implemented for rate limits, HTTP failures, malformed JSON, malformed payloads, and retry attempts.
- Preserve paper-runner progress when fresh public price endpoints fail but discovery already captured usable binary prices, while keeping stale fallback opt-in and explicit in diagnostics. Done with `stale_supported` diagnostics and a `price_refresh_failed_used_stored_snapshot` runner count when the fallback is enabled.
- Add tests using captured fixture payloads, not live network calls.
- Add an aggregated diagnostics endpoint for recent public paper-run skip reasons and source-price limitations. Done.
- Document what real market data is used and which live-execution capabilities are intentionally not enabled yet.

Done when:

- The project can ingest real public weather-market metadata and price snapshots into stored records.
- The same workflow still works offline with mock or fixture data.
- Source limitations are documented instead of hidden.
- The project can support real market data while live execution remains disabled by default.

Portfolio value:

- Shows practical integration with a real market-data source.
- Strengthens the project beyond a toy demo while keeping it safe and reviewable.
- Creates a clean boundary between research data, paper trading, and future live execution.

## Phase 7: Portfolio Polish

Status: partially implemented.

Objective: make the project easy to evaluate quickly.

Work:

- Add a demo seed command or scripted API flow. Initial scripted workflow is implemented.
- Tighten README around setup, demo, technical highlights, and the paper-trading boundary. Initial architecture overview, smoke-demo output, backtest output, and observed-outcome boundary notes are implemented.
- Keep API workflow documentation current. Initial workflow documentation is current with the implemented paper-trading and backtest paths.
- Add architecture and data-model diagrams if useful.
- Add sample outputs for the main workflow. Initial scripted workflow and seed backtest sample outputs are documented.
- Add a concise interview walkthrough. Initial demo plan and positioning docs are implemented.
- Add a short "why this matters" section for backend/data/AI roles.

Done when:

- A reviewer can run the project locally and see the core workflow in under 10 minutes.
- The README explains the project's backend, data, and AI/ML relevance clearly.
- The docs support a 2-3 minute verbal walkthrough.

Portfolio value:

- Converts working software into a readable portfolio artifact.
- Reduces reviewer setup friction.
- Makes the technical story easy to evaluate quickly.

## Phase 8: Optional Frontend Dashboard

Status: started with a read-only dashboard.

Objective: add a visual demo only after the backend workflow is compelling.

Work:

- Build a compact dashboard for markets, forecasts, predictions, backtest/calibration metrics, opportunities, and paper trades. Initial read-only Vite + React dashboard is implemented.
- Use `GET /dashboard/summary` as the first dashboard data contract. Done for the initial dashboard.
- Show the end-to-end pipeline state for each market. Initial pipeline status is implemented.
- Surface data provenance: parsed target, forecast snapshot, model output, price snapshot, EV recommendation, and public source diagnostics. Initial inline latest-signal and source-diagnostic fields are implemented; deeper market-detail inspection remains a follow-up.
- Surface model evaluation context. Compact backtest metrics, paper replay metrics, calibration buckets, and sample-size notes are implemented through the dashboard summary contract.
- Surface public paper-runner validation history. Recent run status, dry-run mode, workflow counts, skip reasons, and errors are implemented through the dashboard summary contract.
- Keep the UI operational and data-dense, not marketing-focused. Initial pass follows this direction.
- Add safe paper-workflow action buttons after the read-only dashboard is stable. Initial `Run Paper Demo` and `Run Public Dry Run` buttons are implemented; granular workflow controls remain planned.

Done when:

- The frontend improves demo clarity.
- The backend remains the main technical artifact.
- The dashboard can show the full paper-trading research workflow and clearly label any future live-trading state.

Portfolio value:

- Helps non-backend reviewers understand the workflow.
- Provides a polished demo layer without replacing the backend story.

## Phase 9: Live Trading Safety Foundation

Status: planned after paper trading and backtesting are credible.

Objective: add the controls required before any real execution code can be safely implemented in this backend.

Work:

- Add explicit trading mode configuration with paper mode as the default.
- Add environment gating so live mode cannot be enabled accidentally.
- Add credential and secret-management boundaries.
- Add position and exposure limits.
- Add kill-switch behavior.
- Add audit logs for live-intent actions.
- Add execution abstractions that can be tested in paper mode.
- Add tests proving paper mode cannot place live orders.
- Document the minimum evidence required before enabling live execution.
- Keep `TRADING_MODES.md`, `LIVE_TRADING_SAFETY.md`, and `EXECUTION_DESIGN.md` current.

Required controls before live execution:

- Credential and wallet isolation.
- Authenticated exchange integration.
- Order management.
- Position tracking.
- Kill switch.
- Risk limits.
- Monitoring and alerting.
- Audit logs.
- Failure-mode handling.

Done when:

- Paper trading remains the default and is fully functional.
- Live mode requires explicit configuration and cannot be reached accidentally.
- Execution abstractions are tested without placing real orders.
- Audit, limits, and kill-switch behavior are documented and tested.

Portfolio value:

- Shows responsible system boundaries.
- Demonstrates that live trading is treated as risk-bearing backend functionality with real controls.

## Phase 10: Live Trading Execution

Status: future, blocked until Phase 9 is done.

Objective: implement real trading only after the research, paper-trading, backtesting, and safety-control foundation exists.

Work:

- Add authenticated trading client support behind an adapter.
- Add order preview and validation.
- Add real order placement behind explicit live mode.
- Add live position synchronization.
- Add execution result persistence.
- Add operational documentation for live mode.
- Add integration tests against sandbox/testnet APIs where available.

Done when:

- Live order placement is impossible unless live mode is explicitly enabled.
- Paper mode and live mode share strategy inputs but write clearly separate records.
- Every live-intent action is auditable.
- Risk limits and kill switch are enforced before order placement.
- Tests cover failure modes around credentials, network errors, rejected orders, and disabled live mode.

Portfolio value:

- Shows the backend can move from research to controlled execution.
- Demonstrates mature risk thinking around real trading systems.

## Near-Term Recommended Order

1. Implement paper-trading hardening for multi-day runs, starting with price/forecast freshness guards, portfolio limits, outcome eligibility preview, trade signal snapshots, and rehearsal reporting.
2. Continue improving real public market-data integration while preserving paper mode as default.
3. Broaden observed-outcome coverage beyond the initial Open-Meteo archive precipitation resolver.
4. Continue evidence-readiness work beyond the initial report: rolling backtests, market-implied coverage diagnostics, lifecycle counts, and unresolved-past-target-window diagnostics.
5. Keep `LOCAL_DEMO.md` aligned with the working API flow.
6. Polish README and docs for a 10-minute local portfolio review.
7. Add live-trading safety foundation only after paper trading and backtesting evidence exists.
8. Add real execution only after safety controls are implemented and tested.

## Priority Rules

- Prefer work that strengthens the end-to-end demo.
- Prefer persistence, provenance, and tests before new surface area.
- Prefer tests around domain behavior over superficial coverage.
- Prefer explicit model assumptions over black-box complexity.
- Prefer real public market-data integration where it supports the research and trading-readiness workflow.
- Preserve mock and fixture paths so the project remains demoable without network access.
- Keep paper trading as the default mode.
- Do not add live execution without configuration gates, credentials isolation, risk limits, audit logs, kill-switch behavior, and tests.
- Do not add a frontend before the backend workflow is compelling.
- Do not add LLM parsing until the rule-based parser's limits are clear.

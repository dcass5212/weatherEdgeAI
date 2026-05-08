# Portfolio Positioning

## Positioning Statement

WeatherEdge AI is a portfolio-grade backend and applied ML project that turns weather prediction-market questions into structured data, forecast-backed probabilities, expected-value recommendations, paper-trading records, and eventually safety-gated live execution.

It is designed to demonstrate practical engineering skill across API design, data modeling, external data ingestion, probability estimation, and evaluation.

Paper trading is the first and default execution mode. The broader product arc is to validate the research workflow through paper trading and backtesting, then add live trading inside the backend only after safety controls are implemented.

## Roles This Project Supports

This project is most relevant for:

- Backend engineer.
- Python engineer.
- Data engineer.
- ML engineer with backend/API responsibilities.
- Applied AI engineer.
- Quantitative/data product engineer.

It is less directly targeted at frontend-only roles unless a dashboard is added later.

## Skills Demonstrated

- FastAPI application structure and route design.
- Pydantic request/response modeling.
- SQLAlchemy ORM modeling.
- PostgreSQL-backed persistence.
- External API integration with testable adapters.
- Domain parsing from natural-language market questions.
- Forecast normalization and snapshotting.
- Probability modeling and model-versioned outputs.
- Expected-value strategy logic.
- Paper-trading simulation.
- Backtesting, calibration buckets, and paper-trade replay summaries.
- Test-driven domain behavior.
- Documentation of product intent and technical tradeoffs.

## Resume Bullet Candidates

- Built a FastAPI backend that discovers weather prediction markets, parses market questions into structured weather targets, fetches forecast data, and generates paper-trading recommendations.
- Designed SQLAlchemy/PostgreSQL data models for market metadata, parsed targets, forecast snapshots, predictions, EV recommendations, resolved outcomes, and simulated trades.
- Implemented a baseline precipitation probability model with expected-value analysis and test coverage for core strategy behavior.
- Integrated public market and weather data sources through modular clients designed for offline testing and future provider expansion.
- Implemented seed-fixture backtesting with Brier score, log loss, calibration buckets, sample-size notes, and paper-trade replay summaries.
- Added observed-weather outcome normalization for Open-Meteo archive and fixture/manual NOAA/NCEI CDO-style daily precipitation payloads while keeping demos credential-free.

## Interview Talking Points

Strong topics to discuss:

- Why paper trading is implemented first and remains the default.
- How the backend can transition from paper trading to safety-gated live execution.
- How the data model preserves raw API payloads while exposing normalized domain records.
- Why the first parser is rule-based instead of LLM-based.
- How forecast snapshots make predictions reproducible.
- How model versioning supports later model comparisons.
- Why calibration matters more than a single accuracy number.
- How the architecture separates ingestion, parsing, weather, modeling, strategy, and backtesting.
- How tests are structured around domain behavior rather than only endpoint smoke tests.

## Technical Tradeoffs

### Rule-Based Parser First

The project starts with regex/rule-based parsing because the V1 market scope is narrow and predictable. This makes failures inspectable, avoids unnecessary LLM cost, and creates a benchmark for any later LLM parser.

### Baseline Model First

The first model should be transparent and easy to reason about. A simple baseline gives the project a measurable starting point before adding trained ML models.

### Snapshot-Based Forecasts

Forecast snapshots preserve the exact data used by a prediction. This matters for reproducibility, backtesting, and debugging model behavior.

### Paper Trading First

Paper trading keeps local development, demos, tests, and validation safer and more reproducible. It gives the project evidence before any real execution path is enabled.

Live trading is part of the product direction, but it requires explicit live-mode configuration, credential handling, risk controls, monitoring, audit logs, kill-switch behavior, and operational safeguards.

## Demo Narrative

A short demo should show:

1. Discover or seed a weather market.
2. Parse the question into location, metric, operator, threshold, and target window.
3. Fetch and store a forecast snapshot.
4. Run a probability prediction.
5. Compare prediction against market price.
6. Generate an EV recommendation.
7. Create or show a paper trade.
8. Run or show a backtest replay with calibration and paper-trade metrics.

## What Reviewers Should Notice

Reviewers should be able to see that this is not just a CRUD API. The project has a domain workflow, data provenance, model outputs, strategy evaluation, and a path toward measuring whether the model is useful.

## Portfolio Risks To Avoid

- Shipping many endpoints without a clear end-to-end demo.
- Adding a frontend before the backend workflow is reliable.
- Adding an LLM parser before simpler parsing is exhausted.
- Claiming trading performance without backtesting and paper-trading evidence.
- Adding live execution before paper trading, backtesting, and safety gates are credible.
- Letting docs drift from implementation.
- Treating probability outputs as certainty.

## Portfolio Finish Line

The project is portfolio-ready when:

- The README explains the problem, architecture, setup, and demo clearly.
- A local demo runs from fresh setup.
- Tests pass.
- The main workflow produces persisted records across the database.
- The model and EV logic are documented.
- Backtesting or calibration output exists, even if based on a small seed dataset.
- The project can be explained in under 3 minutes and defended in a deeper technical interview.
- The path from paper trading to safety-gated live execution is documented.

## Current Review Path

A reviewer can run `scripts/demo_workflow.py --sqlite-memory` to see the end-to-end paper workflow without PostgreSQL, then run the full test suite and seed-fixture backtest with PostgreSQL for a deeper review. The expected story is working backend data flow and evaluation discipline, not proven trading profitability.

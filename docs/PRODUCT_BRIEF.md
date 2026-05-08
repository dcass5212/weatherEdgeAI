# Product Brief

## Summary

WeatherEdge AI is a backend-focused system for weather-related prediction markets. It discovers weather markets, parses market questions into structured targets, fetches forecasts, estimates event probabilities, compares those probabilities with market prices, supports paper-trading validation, and is intended to grow into live trading with explicit safety controls.

The project exists primarily as a portfolio piece for backend, data, and applied AI/ML roles. It should demonstrate judgment, architecture, testability, and responsible engineering more than speculative trading behavior.

WeatherEdge AI should create a clean foundation for live trading inside this backend, but only after the paper-trading and backtesting workflow is credible. Paper trading remains the default mode for development, tests, demos, and strategy validation.

## Target User

The primary user is a research-oriented analyst who wants to evaluate weather prediction markets with a repeatable data pipeline instead of manual judgment.

Secondary users are hiring managers and engineers reviewing the project. For them, the project should make the system design, tradeoffs, and implementation quality easy to inspect.

## Core Workflow

1. Discover active weather-related markets from a market data source.
2. Persist source market metadata and market price snapshots.
3. Parse a natural-language market question into a structured weather target.
4. Fetch a forecast for the parsed location and target window.
5. Normalize the forecast into a snapshot used by the model.
6. Estimate the probability that the market resolves YES.
7. Compare model probability with market prices.
8. Generate an expected-value recommendation and simulated paper position.
9. Later, compare predictions and paper trades against resolved outcomes.
10. After validation and safety controls exist, route approved recommendations through live execution.

## V1 Scope

V1 focuses on precipitation threshold markets, such as:

- Will New York City get more than 1 inch of rain on May 5?
- Will Chicago receive at least 0.5 inches of rain tomorrow?

V1 should support an end-to-end backend demo with seeded or discoverable markets, parsed targets, forecast snapshots, baseline probabilities, EV calculations, and paper-trade records.

## Execution Scope

Paper trading is in scope immediately and must be implemented first.

Live trading is in scope only after the backend has safety controls:

- Explicit paper/live mode configuration that defaults to paper.
- Credential and secret isolation.
- Position and exposure limits.
- Kill-switch behavior.
- Audit logs.
- Tests proving paper mode cannot place live orders.

Financial advice claims remain out of scope.

## Live-Trading Progression

The intended progression is:

1. Build a strong paper-trading research platform in this repository.
2. Use backtests, calibration, and paper-trading results to identify whether the strategy has enough signal to justify further work.
3. Add live-trading safety foundations in this backend.
4. Add authenticated execution only after the safety foundation is implemented and tested.

Live trading requires authentication design, execution limits, audit logging, operational monitoring, kill switches, secret management, and risk controls. These concerns should be implemented deliberately, not added as incidental route behavior.

## Portfolio Value

This project should show:

- Clean FastAPI route design.
- SQLAlchemy domain modeling and persistence.
- Data ingestion from external APIs.
- Natural-language parsing into structured data.
- Forecast normalization.
- Probability modeling with clear assumptions.
- Expected-value and risk-aware recommendation logic.
- Backtesting and calibration methodology.
- Tests that cover core business behavior.
- Documentation that explains product intent, architecture, and tradeoffs.

## Design Principles

- Prefer boring, inspectable architecture over cleverness.
- Keep domain boundaries clear: markets, weather, modeling, strategy, backtesting.
- Make services easy to test without network access.
- Build the baseline first, then improve it with evidence.
- Treat probability outputs as estimates with measurable calibration.
- Keep the app demoable at every major phase.
- Keep live-execution concerns safety-gated and separate from paper-trading records.

## Assumptions To Revisit

- Initial market source is a Polymarket-style public market API.
- Initial weather source is Open-Meteo.
- Initial parser is regex/rule-based, not LLM-based.
- Initial model is a transparent baseline, not trained ML.
- A frontend is optional until the backend demo is strong.
- Live trading belongs after paper-trading validation and safety controls.

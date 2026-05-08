# Architecture

## Module Map

- `app.main`: FastAPI application factory point and router registration.
- `app.api`: HTTP routes for health, markets, predictions, and strategy.
- `app.config`: Typed settings loaded from environment variables and `.env`.
- `app.db`: SQLAlchemy ORM base, session wiring, and domain models.
- `app.markets`: Prediction-market API access, discovery, parsing, and market schemas.
- `app.weather`: Weather forecast API access and forecast schemas.
- `app.modeling`: Probability estimation and model evaluation helpers.
- `app.strategy`: Edge, expected value, risk sizing, paper trade generation, and later safety-gated execution abstractions.
- `app.backtesting`: Future historical market replay tools.

## Data Flow

1. Discover active weather-related markets from market data sources.
2. Parse market questions into structured weather targets.
3. Fetch forecasts for the parsed location and target window.
4. Estimate the probability that the market resolves YES.
5. Fetch market prices and calculate model edge and expected value.
6. Create paper-trading recommendations for later evaluation.
7. Compare predictions and paper trades against resolved outcomes.
8. After validation and safety controls exist, route approved recommendations through live execution.

## Database Tables

- `markets`: Source market metadata and status.
- `parsed_markets`: Structured weather targets extracted from questions.
- `market_price_snapshots`: YES/NO prices, spread, and liquidity over time.
- `weather_forecast_snapshots`: Forecast values used by models.
- `predictions`: Model probabilities and feature payloads.
- `ev_recommendations`: Expected value outputs and paper position sizing.
- `resolved_outcomes`: Final market outcomes and observed values.
- `paper_trades`: Simulated positions for paper-trading evaluation.
- Future live execution tables should remain separate from paper-trading records and require explicit live-mode safety controls.

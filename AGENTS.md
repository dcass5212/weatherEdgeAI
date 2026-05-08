# AGENTS.md

## Purpose

WeatherEdge AI is a portfolio-grade FastAPI backend for weather prediction markets. It discovers markets, parses weather questions, fetches forecasts, estimates probabilities, evaluates expected value, supports paper trading, and is intended to grow into a live-trading-capable backend.

Paper trading must be implemented first and remain the default mode for local development, tests, demos, and strategy validation.

## Read First

At the start of a substantial session, read:

- `README.md`
- `docs/ROADMAP.md`
- `docs/API_WORKFLOWS.md`
- `docs/TRADING_MODES.md`
- `docs/LIVE_TRADING_SAFETY.md`
- `docs/DATA_MODEL.md`
- `docs/TECHNICAL_DECISIONS.md`

Use `docs/ROADMAP.md` as the source of truth for current priorities.

## Product Boundary

The backend may be designed for both paper trading and live trading, but live execution must not be added casually.

Before real order placement, wallet signing, authenticated trading APIs, or live position management are implemented, the codebase must have:

- Paper-trading flow working end to end.
- Backtesting or replay support with meaningful metrics.
- Explicit configuration that defaults to paper mode.
- Environment gating for any live execution mode.
- Credential and secret isolation.
- Position and exposure limits.
- Kill-switch behavior.
- Audit logs for live-intent actions.
- Tests that prove paper mode cannot accidentally place live orders.

## Architecture

- `app/api`: FastAPI route modules.
- `app/config.py`: Environment-backed application settings.
- `app/db`: SQLAlchemy base, session, repositories, and ORM models.
- `app/markets`: Market clients, discovery, schemas, and parsing.
- `app/weather`: Forecast clients, normalization, and schemas.
- `app/modeling`: Probability models, metrics, and calibration.
- `app/strategy`: Expected value, risk sizing, paper trading, and later execution abstractions.
- `app/backtesting`: Historical replay, outcomes, and reports.

Keep external systems behind small client or adapter modules. Preserve raw source payloads where useful for debugging and reproducibility.

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
- Alembic

## Commands

Setup:

```powershell
cd C:\weatherEdgeAI\backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create local env:

```powershell
cd C:\weatherEdgeAI
Copy-Item .env.example .env
```

Run database:

```powershell
cd C:\weatherEdgeAI
docker compose up -d
```

Run backend:

```powershell
cd C:\weatherEdgeAI\backend
uvicorn app.main:app --reload
```

Run tests:

```powershell
cd C:\weatherEdgeAI\backend
.\.venv\Scripts\pytest
```

## Coding Expectations

- Follow existing module boundaries.
- Prefer simple, testable services over broad abstractions.
- Use Pydantic schemas for API contracts.
- Use SQLAlchemy models for persisted domain state.
- Add Alembic migrations for schema changes once Alembic is introduced.
- Keep calculations small and directly tested.
- For important code files, add a short top-of-file comment section explaining what the file does and why it exists, assuming the reader has little context about weather markets, prediction modeling, trading modes, or this project.
- Comment code when intent is not obvious; use short section-level explanations for larger or riskier logic blocks.
- Do not claim trading performance without backtesting and paper-trading evidence.
- Keep docs aligned with behavior when product scope, workflows, or architecture changes.
- Document each Codex-assisted implementation change in `CHANGELOG.md` after each prompt.

## Implementation Bias

- Prefer end-to-end workflow improvements over isolated features.
- Prefer persisted, inspectable records over transient-only calculations.
- Prefer fixture-backed tests over live network tests.
- Keep mock and paper-mode paths working for demos and local review.
- Prefer explicit safety gates over implicit assumptions for trading behavior.
- Avoid new abstractions unless they clarify the workflow or reduce real duplication.

## Docs Ownership

- Roadmap or priority changes: update `docs/ROADMAP.md`.
- API behavior or endpoint flow changes: update `docs/API_WORKFLOWS.md`.
- Schema, persistence, or relationship changes: update `docs/DATA_MODEL.md`.
- Trading mode changes: update `docs/TRADING_MODES.md`.
- Live execution or safety-control changes: update `docs/LIVE_TRADING_SAFETY.md` and `docs/EXECUTION_DESIGN.md`.
- Demo flow changes: update `docs/LOCAL_DEMO.md` and `docs/DEMO_PLAN.md`.
- Modeling, metrics, or calibration changes: update `docs/MODELING_PLAN.md` and `docs/BACKTESTING_SPEC.md` where relevant.
- Major architectural decisions: update `docs/TECHNICAL_DECISIONS.md`.

## Portfolio Definition Of Done

A substantial change is portfolio-ready when:

- The implementation matches the requested behavior.
- Relevant tests pass locally.
- New domain behavior has focused tests.
- The local demo path still works or docs explain the limitation.
- API responses remain readable for a reviewer.
- Implemented behavior is distinguishable from planned behavior in docs.
- Paper mode remains the default for trading workflows.
- Any live-trading change has configuration gates, auditability, limits, kill-switch behavior, and tests.

## Portfolio Communication Rules

- Be explicit about what is implemented versus planned.
- Do not overstate model quality or trading performance.
- Call out limitations directly in docs and demo notes.
- Explain safety gates before discussing live trading.
- Keep the portfolio story focused on backend architecture, reproducible data flow, probability modeling, evaluation, and responsible execution design.

## Session Startup Checklist

For substantial work:

1. Read `AGENTS.md`.
2. Read `docs/ROADMAP.md`.
3. Read the relevant docs listed in the Read First section.
4. Inspect the current implementation before editing.
5. Check tests related to the intended change.
6. Update docs and run targeted tests before finalizing.

## Testing Priorities

Prioritize tests for:

- Parser behavior.
- Forecast normalization.
- Repository persistence.
- Probability calculations.
- EV and risk logic.
- Paper-trading workflow.
- Backtest metrics.
- Live-trading safety gates before any real execution code exists.

External network calls should be mockable or fixture-backed.

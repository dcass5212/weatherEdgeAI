# Contributing For Codex

## Purpose

This document gives Codex and future contributors the operating context for WeatherEdge AI. The primary goal is to build a portfolio-grade backend project that helps the owner land a software engineering job.

Implementation choices should support that goal directly.

The project should preserve a clean path to live trading inside this backend. Paper trading must be implemented first, remain the default mode, and stay available after live trading is added.

## Project Priorities

1. Make the end-to-end backend workflow work.
2. Keep the architecture easy to explain.
3. Preserve testability and reproducibility.
4. Document major decisions.
5. Add polish only after the core workflow is credible.

## Current Product Boundary

WeatherEdge AI is a live-trading-capable backend in progress, with paper trading as the first and default execution mode.

Do not add real execution casually. Before wallet signing, authenticated order placement, live position management, or automated execution exists, the project must have:

- Paper trading working end to end.
- Backtesting or replay metrics.
- Explicit configuration that defaults to paper mode.
- Credential and secret isolation.
- Position and exposure limits.
- Kill-switch behavior.
- Audit logs.
- Tests proving paper mode cannot place live orders.

Financial advice language remains out of scope.

## Trading Mode Boundary

WeatherEdge AI may include:

- Paper-trading recommendations and trades.
- Backtesting reports.
- Calibration metrics.
- Research APIs that expose predictions and recommendations.
- Documentation describing live-execution requirements.
- Safety-gated execution abstractions.
- Live execution only after controls are implemented and tested.

When in doubt, implement paper mode first and ask before adding live execution behavior.

## Coding Conventions

- Follow the existing module boundaries under `app/api`, `app/db`, `app/markets`, `app/weather`, `app/modeling`, `app/strategy`, and `app/backtesting`.
- Prefer small services and pure functions where possible.
- Keep external API calls behind client or adapter modules.
- Preserve raw external payloads when useful for debugging.
- Use Pydantic schemas for API inputs and outputs.
- Keep SQLAlchemy models focused on persisted domain state.
- Avoid adding new frameworks unless they clearly reduce project risk.

## Testing Expectations

Every meaningful behavior change should include focused tests.

Prioritize tests for:

- Parser behavior.
- Forecast normalization.
- Repository persistence behavior.
- Probability calculations.
- EV and risk logic.
- Backtest metrics.
- API workflow smoke tests.

Avoid tests that only duplicate implementation details without protecting behavior.

## Documentation Expectations

Update docs when changing:

- Product scope.
- Public API workflows.
- Data model relationships.
- Modeling assumptions.
- Backtesting methodology.
- Demo setup.
- Major technical decisions.

Keep docs concise and truthful. Portfolio reviewers can tell when docs overstate the implementation.

## Definition Of Done

A change is done when:

- The implementation matches the requested behavior.
- Tests pass locally where practical.
- New or changed behavior has appropriate tests.
- Docs are updated if the change affects workflow, architecture, or roadmap.
- Paper mode remains the default and is not bypassed accidentally.
- The result supports the portfolio story.

## Decision Rules

When choosing between possible next tasks:

- Prefer the task that makes the end-to-end demo more complete.
- Prefer stored, inspectable records over transient-only calculations.
- Prefer a simple baseline with tests over complex unvalidated logic.
- Prefer improving existing modules over adding parallel abstractions.
- Prefer backend credibility over visual polish until the core workflow is strong.

## Current Recommended Next Work

1. Add Alembic migrations.
2. Make market discovery persist discovered markets idempotently.
3. Store market price snapshots.
4. Add geocoding behind an adapter.
5. Normalize Open-Meteo responses into forecast snapshots.
6. Connect prediction and EV routes to stored latest inputs.
7. Replace placeholder backtesting with a minimal replay and metrics report.

## Questions To Ask The User

Ask before making decisions that affect:

- Which job role the project should optimize for if tradeoffs differ.
- Whether to add a frontend before backend completion.
- Whether to use an LLM parser.
- Whether to add a paid or authenticated API.
- Whether to introduce a new major dependency.
- Whether to add wallet/signing, credentials, order placement, live positions, or automated execution.
- Whether to change anything that could blur the boundary between paper trading and live execution.

For ordinary backend implementation details, make a conservative decision that fits the existing architecture and proceed.

## Review Checklist

Before finishing a substantial change, check:

- Does this make the portfolio stronger?
- Can this be explained clearly in an interview?
- Is the behavior covered by tests?
- Is the API response useful for a demo?
- Are model assumptions explicit?
- Are external data dependencies mockable?
- Does paper mode remain the default?
- If live execution is touched, are configuration gates, credentials isolation, limits, audit logs, kill switch, and tests present?

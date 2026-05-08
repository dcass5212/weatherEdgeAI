# Technical Decisions

## Purpose

This document records the major engineering decisions behind WeatherEdge AI. It should help future work stay coherent and give interviewers a clear view into the tradeoffs behind the system.

## Decision 1: Paper Trading First, Live Capable Later

WeatherEdge AI should be live-trading capable over time, but paper trading is the first and default execution mode.

Rationale:

- The project needs credible research, modeling, and paper-trading validation before real execution.
- Paper trading keeps local development, tests, and demos deterministic and safe.
- Live trading is risk-bearing functionality and needs explicit controls before it is implemented.

Implications:

- Paper mode must be the default.
- Paper-trading records and live execution records must be distinct.
- Live mode must require explicit configuration.
- Credentials, wallet/signing, order placement, and live positions must be isolated behind safety-gated adapters.
- Strategy outputs should be validated through backtesting and paper trading before live execution.

Future revisit:

- After this project has credible backtesting, calibration, and paper-trading records, add the live-trading safety foundation: configuration gates, audit logging, monitoring, kill switches, position limits, and secret-management boundaries.

## Decision 2: FastAPI For The Backend

WeatherEdge AI uses FastAPI as the HTTP API framework.

Rationale:

- Strong fit for Python data and ML workflows.
- Pydantic integration makes request and response contracts explicit.
- OpenAPI docs are useful for portfolio review and manual testing.
- Async support is useful for external API clients.

Tradeoff:

- FastAPI is not a complete application platform. The project still needs deliberate decisions around persistence, migrations, background jobs, and operational workflows.

## Decision 3: SQLAlchemy ORM With PostgreSQL

The project uses SQLAlchemy ORM models and PostgreSQL as the intended production-style database.

Rationale:

- The domain has clear relationships: markets, parsed targets, snapshots, predictions, recommendations, outcomes, and trades.
- SQLAlchemy is widely recognized and interview-relevant.
- PostgreSQL is a credible default for relational, auditable records.

Tradeoff:

- ORM models need migrations to be production credible. Alembic is a near-term roadmap item.

## Decision 4: Snapshot-Based Data Design

Market prices, forecasts, predictions, and recommendations are modeled as time-stamped records.

Rationale:

- Predictions need reproducible inputs.
- Backtesting needs historical-like records.
- Calibration requires knowing which model version produced each probability.
- Paper-trade evaluation needs entry and exit state.

Implications:

- Do not overwrite prediction history.
- Preserve raw external payloads where useful.
- Link outputs back to the source snapshot used to produce them.

## Decision 5: Rule-Based Parser First

The initial parser is regex/rule-based and focused on precipitation threshold markets.

Rationale:

- V1 question formats are narrow enough for explicit parsing.
- Rule-based parsing is cheap, testable, and inspectable.
- Failures can be described clearly.
- It creates a baseline before considering an LLM parser.

Tradeoff:

- Coverage is limited but expanding through fixture-backed cases. The parser will need continued real-market failure capture or a fallback strategy for broader market wording.

Future revisit:

- Consider an LLM parser only after rule-based parser failures are collected and categorized.

## Decision 6: Open-Meteo As Initial Weather Source

Open-Meteo is the initial forecast provider.

Rationale:

- Public and accessible.
- Good fit for a portfolio demo.
- Provides daily precipitation fields needed for V1.

Tradeoff:

- Forecast quality and historical replay support may be limited for advanced backtesting. Normalization is deliberately defensive so malformed or partial provider payloads do not crash the workflow.

Future revisit:

- Add NOAA/NWS observed weather data for outcome verification and calibration.

## Decision 6A: Fixture Geocoder Before Optional External Geocoding

The parse workflow resolves known demo locations through a deterministic fixture geocoder before calling weather APIs. A broader Open-Meteo geocoder exists behind the same adapter and is opt-in through configuration.

Rationale:

- Forecast requests require latitude and longitude.
- Tests and local demos should not depend on a live geocoding provider.
- Keeping geocoding outside the parser lets the parser focus on extracting structured market terms.
- Broader location coverage is useful for manual public-market review, but should not make the default demo path flaky.

Tradeoff:

- Default location coverage is intentionally limited. Broader coverage requires `GEOCODING_PROVIDER=open_meteo`, and provider failures are surfaced as external dependency errors rather than hidden.

## Decision 7: Transparent Baseline Model First

The initial precipitation model is a simple threshold-based baseline.

Rationale:

- The project needs an end-to-end prediction pipeline before advanced ML.
- Simple model behavior is easy to explain in interviews.
- Calibration metrics can compare future models against the baseline.

Tradeoff:

- The baseline is not expected to be highly predictive. Its purpose is to establish infrastructure and evaluation.

Future revisit:

- Add trained models only after enough forecast snapshots and resolved outcomes exist.

## Decision 8: Tests Focus On Domain Behavior

Tests should protect parser logic, forecast normalization, probability estimates, EV calculations, persistence behavior, and API workflow behavior.

Rationale:

- Portfolio reviewers care that important behavior is reliable.
- Domain tests are more valuable than tests that only mirror implementation details.

Implications:

- External clients should be mockable.
- Core calculations should stay small and testable.
- Route tests should cover workflow failures as well as happy paths.

## Decision 9: Frontend Comes After Backend Credibility

A dashboard is optional and should come after the backend workflow is strong.

Rationale:

- The target portfolio signal is backend/data/applied ML.
- A weak backend with a polished UI would undercut the project.
- A later dashboard can make the demo clearer once the data flow is real.

Future revisit:

- Add a compact dashboard after market ingestion, forecast snapshots, predictions, EV recommendations, and paper trades are working end to end.

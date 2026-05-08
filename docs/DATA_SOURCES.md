# Data Sources

## Market Data

V1 is designed around Polymarket-style market data for active events, market questions, market status, and market price snapshots.

The first implementation uses public market-data clients and mock data for deterministic tests and demos. Authenticated trading APIs are a later phase after paper trading and safety controls are in place.

Price snapshot normalization is fixture-backed for representative public Polymarket-style shapes:

- Gamma market records with `outcomes` and `outcomePrices`.
- Gamma event-wrapped weather markets where the child market question may rely on parent event title, category, or tags for weather context.
- CLOB orderbook payloads with bid and ask levels.
- CLOB token price maps where `BUY` represents the best ask and `SELL` represents the best bid for YES/NO token IDs.
- Fresh CLOB token price maps that rely on stored Gamma market context for outcome and token-id metadata.
- Malformed Gamma-style price fields where diagnostics should show parse failures even when liquidity or volume fields are still usable.

These fixtures preserve the offline demo/test path and do not require authenticated order placement.

Market ingestion now also persists `source_diagnostics` on each market. Diagnostics record whether the source payload exposed usable market metadata, condition IDs, binary YES/NO prices, top-of-book data, liquidity, volume, status, and resolution metadata. Unsupported or partial price payloads keep explicit reasons such as `no_supported_price_fields`, `price_fields_not_parseable`, or `missing_binary_yes_no_prices` so integration gaps can be debugged from stored records.

Price refresh is read-only. For Polymarket-sourced markets, `POST /markets/{market_id}/price-snapshots/refresh` fetches a fresh public payload through the market-data client, combines it with stored market context when fresh token prices need outcome/token metadata, normalizes it, persists a new immutable price snapshot, and updates source diagnostics. For manually seeded or non-public markets, the route still supports stored-payload refresh so local demos and fixture-backed review do not require network access.

## Weather Forecasts

Open-Meteo forecasts are the initial weather source. The V1 forecast client requests daily precipitation and temperature fields for a latitude, longitude, and date range.

## Geocoding

Fixture geocoding remains the default for local demos and tests. It resolves known demo locations without network access.

Open-Meteo geocoding is implemented as an optional public provider behind the same adapter. Set `GEOCODING_PROVIDER=open_meteo` during manual runs to let parsing enrich broader locations with latitude and longitude. Tests mock this provider rather than calling the live API.

## Observed Weather Outcomes

Open-Meteo archive is the initial observed-weather source for resolving parsed precipitation markets. The resolver requests daily precipitation totals, preserves the raw provider payload, converts millimeters to inches when the market threshold is in inches, and stores a source-attributed `resolved_outcomes` record.

The resolver also supports fixture/manual NOAA/NCEI CDO-style daily observation payloads that contain `PRCP` records and explicit precipitation units. This broadens observed-outcome normalization without adding token-gated live NOAA API calls yet.

Tests use fixture-style and mocked payloads rather than live network calls.

## Future NOAA/NWS Support

Future versions can add a credential-gated NOAA or National Weather Service client for observed outcomes, verification, and richer forecast features.

## Trading API Progression

WeatherEdge AI should support paper trading first. Paper mode is the default for local development, tests, demos, and validation.

Authenticated trading APIs may be added later in this repository only after credential management, wallet/signing isolation, order management, monitoring, kill-switch behavior, audit logs, and risk limits are designed and tested. Tests must prove paper mode cannot place real orders.

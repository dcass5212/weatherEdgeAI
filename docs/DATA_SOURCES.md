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

Price refresh is read-only. For Polymarket-sourced markets, `POST /markets/{market_id}/price-snapshots/refresh` fetches a fresh public payload through the market-data client, combines it with stored market context when fresh token prices need outcome/token metadata, normalizes it, persists a new immutable price snapshot, and updates source diagnostics. Public requests use a small retry budget for transient failures and rate limits. If a public refresh still fails, the market keeps `source_refresh_failed` diagnostics with the endpoint, failure reason, attempt count, status code when available, and retryable flag. For manually seeded or non-public markets, the route still supports stored-payload refresh so local demos and fixture-backed review do not require network access.

## Weather Forecasts

Open-Meteo forecasts are the initial weather source. The V1 forecast client requests daily precipitation and temperature fields for a latitude, longitude, and date range.

## Geocoding

Fixture geocoding remains the default for local demos and tests. It resolves known demo locations without network access.

Open-Meteo geocoding is implemented as an optional public provider behind the same adapter. Set `GEOCODING_PROVIDER=open_meteo` during manual runs to let parsing enrich broader locations with latitude and longitude. Tests mock this provider rather than calling the live API.

## Observed Weather Outcomes

Open-Meteo archive is the default observed-weather source for resolving parsed precipitation markets. The resolver requests daily precipitation totals, preserves the raw provider payload, converts millimeters to inches when the market threshold is in inches, and stores a source-attributed `resolved_outcomes` record.

The resolver also supports NOAA/NCEI CDO-style daily observation payloads that contain `PRCP` records and explicit precipitation units. A credential-gated `noaa_cdo_daily` client is available behind the resolver interface for manual observed-outcome resolution. It requires `NOAA_CDO_TOKEN`, is not used by the default demo path, and is covered by mocked tests rather than live network calls.

Tests use fixture-style and mocked payloads rather than live network calls.

Future versions can add richer NOAA/NWS coverage for station selection, provider diagnostics, and additional observed weather fields.

### Provider Selection

Observed weather resolution is selected per API request through `resolution_provider`:

- `open_meteo_archive`: default provider. No credentials required.
- `noaa_cdo_daily`: optional NOAA/NCEI CDO provider. Requires `NOAA_CDO_TOKEN`.

Open-Meteo request body:

```json
{
  "market_id": 1,
  "resolution_provider": "open_meteo_archive"
}
```

NOAA request body:

```json
{
  "market_id": 1,
  "resolution_provider": "noaa_cdo_daily"
}
```

Required NOAA environment:

```env
NOAA_CDO_BASE_URL=https://www.ncei.noaa.gov/cdo-web/api/v2
NOAA_CDO_TOKEN=your_token_here
```

The NOAA client sends read-only CDO data requests for `GHCND` daily `PRCP` records. It uses metric units, maps the payload into the same daily precipitation normalization path used by fixture/manual NOAA-style payloads, and stores the original provider response for reproducibility.

### Failure Modes

- Missing parsed market: the API returns `409` because there is no structured weather target to resolve.
- Missing latitude, longitude, or target dates: the API returns `422`.
- Missing `NOAA_CDO_TOKEN` for `noaa_cdo_daily`: the API returns `422` before making a NOAA request.
- Provider HTTP or network failure: the API returns `502`.

### Current NOAA Boundary

The NOAA CDO client is a provider boundary, not a finished station-selection engine. It queries a small coordinate bounding box around the parsed market location and accepts returned `PRCP` records. That is enough to prove the adapter, credential gate, normalization, and persistence path, but portfolio claims should not imply that station selection is production-grade yet.

## Trading API Progression

WeatherEdge AI should support paper trading first. Paper mode is the default for local development, tests, demos, and validation.

Authenticated trading APIs may be added later in this repository only after credential management, wallet/signing isolation, order management, monitoring, kill-switch behavior, audit logs, and risk limits are designed and tested. Tests must prove paper mode cannot place real orders.

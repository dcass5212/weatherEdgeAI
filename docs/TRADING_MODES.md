# Trading Modes

## Purpose

WeatherEdge AI should support paper trading first and live trading later. This document defines what each trading mode means so execution behavior is explicit, testable, and safe.

## Supported Modes

### `paper`

Default mode for local development, tests, demos, and strategy validation.

Allowed behavior:

- Create simulated paper trades.
- Close simulated paper trades.
- Evaluate paper-trading PnL.
- Use mock, fixture, or public market data.
- Exercise execution-like logic through paper adapters.

Forbidden behavior:

- Real order placement.
- Wallet signing.
- Authenticated exchange execution.
- Live position mutation.
- Credential access required only for real execution.

### `live`

Future mode for real execution. This mode is blocked until the live-trading safety foundation is implemented.

Allowed behavior after safety gates exist:

- Read authenticated account/exchange state.
- Preview and validate orders.
- Place real orders through a live execution adapter.
- Persist live execution records separately from paper trades.
- Sync live positions.

Required before enabling:

- Explicit configuration that defaults off.
- Credential and secret isolation.
- Position and exposure limits.
- Kill-switch behavior.
- Audit logs.
- Tests proving paper mode cannot place live orders.

### `read_only`

Optional future mode for authenticated data access without execution.

Allowed behavior:

- Read account, balance, position, or order state if credentials are configured.
- Persist read-only observations.

Forbidden behavior:

- New order placement.
- Order cancellation.
- Wallet signing.
- Position mutation.

## Defaults

Paper mode is the default. If configuration is missing, malformed, or ambiguous, the system should behave as paper mode or fail closed.

Live mode must require an explicit setting such as:

```text
TRADING_MODE=live
```

Live mode should also require additional confirmation settings before order placement, such as:

```text
LIVE_TRADING_ENABLED=true
```

The exact names can change during implementation, but the rule should not: live execution requires explicit opt-in.

## Records

Paper and live records must stay separate.

- Paper trades represent simulated positions.
- Live execution records represent real orders, fills, cancellations, and positions.
- EV recommendations can feed both modes, but recommendations should not be mutated into orders.

## Tests

Every live-capable execution path must include tests for:

- Default configuration uses paper mode.
- Paper mode cannot place live orders.
- Missing credentials fail before order placement.
- Disabled live mode fails before order placement.
- Kill switch blocks live order placement.
- Position limits block oversized orders.

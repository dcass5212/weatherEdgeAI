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
- Use simple simulated risk sizing from EV recommendations.
- Use mock, fixture, or public market data.
- Exercise execution-like logic through paper adapters.
- Run guarded one-shot public-market paper passes that create only simulated paper trades within configured caps.
- Persist public paper-run history for auditability and automated validation.
- Manually opt in to experimental interval precipitation contracts for paper-runner research while keeping the default off.

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

Current configuration:

```text
TRADING_MODE=paper
LIVE_TRADING_ENABLED=false
```

The application settings expose `live_execution_allowed`, which is true only when `TRADING_MODE=live` and `LIVE_TRADING_ENABLED=true`. There is still no live execution adapter or order-placement endpoint; this is only the first explicit configuration gate for future live work.

Current paper sizing is deliberately simple and research-only. Actionable EV recommendations convert positive probability edge into simulated units by multiplying edge by 100 and capping the result at 10 units. This cap is not a live-trading risk limit; live execution still requires separate safety controls, audit logging, kill-switch behavior, and tested exposure limits.

The public paper runner also applies conservative paper portfolio limits by default: 5 open simulated trades, 25 total simulated exposure, 5 per market, and 10 per parsed location. These limits are designed for research realism and small-bankroll discipline only. They do not replace the separate live-mode risk limits required before real execution.

Paper entry slippage is optional and defaults to zero. When enabled for research, it adjusts simulated paper fill prices while preserving the quoted entry price in the trade's signal snapshot. This is still a paper-only assumption, not a live execution model.

Future live mode must require an explicit setting such as:

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

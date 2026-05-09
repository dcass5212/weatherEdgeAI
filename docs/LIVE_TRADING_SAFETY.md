# Live Trading Safety

## Purpose

Live trading is risk-bearing functionality. WeatherEdge AI may become live-trading capable, but real execution must be blocked until the safety foundation exists and is tested.

## Safety Foundation

Before live order placement exists, the backend must have:

- Paper trading working end to end.
- Backtesting or replay metrics for the strategy.
- Trading mode configuration that defaults to paper.
- Environment gating for live mode.
- Credential and secret isolation.
- Order preview and validation.
- Position and exposure limits.
- Kill-switch behavior.
- Audit logs for live-intent actions.
- Tests proving paper mode cannot place live orders.

## Configuration Gates

Live execution should require more than one intentional signal.

Recommended gates:

- `TRADING_MODE=live`
- `LIVE_TRADING_ENABLED=true`
- Valid live execution credentials.
- Kill switch not active.
- Risk limits configured.

If any gate is missing, the system should fail before order placement.

Current implementation status:

- `TRADING_MODE` exists and defaults to `paper`.
- `LIVE_TRADING_ENABLED` exists and defaults to `false`.
- The current settings helper only reports live execution as allowed when both values are explicitly enabled.
- No authenticated trading client, live execution adapter, order-placement route, wallet signing, live positions, kill switch, audit log, or exposure-limit enforcement has been implemented yet.

## Credential Handling

Credentials must not be stored in source files, fixtures, test snapshots, or logs.

Implementation expectations:

- Load secrets from environment or a dedicated secret manager.
- Keep authenticated clients behind adapter modules.
- Never expose private keys or tokens in API responses.
- Redact credentials in logs and error messages.
- Keep paper mode independent of live credentials.

## Order Safety

Before sending any live order, the backend should validate:

- Trading mode is live.
- Live execution is enabled.
- Kill switch is inactive.
- Market is supported.
- Side is valid.
- Quantity is positive.
- Price is within allowed bounds.
- Position and exposure limits are not exceeded.
- The order links to an approved recommendation or explicit manual request.

## Kill Switch

The kill switch should block new live orders immediately.

Minimum behavior:

- New order placement is rejected.
- Audit log records the rejection.
- Existing paper-trading workflows continue.

Future behavior may include order cancellation or position reduction, but those actions also require explicit design and tests.

## Audit Logs

Live-intent actions should be auditable even when blocked.

Audit records should capture:

- Timestamp.
- Trading mode.
- Actor or system source.
- Intended action.
- Market/order identifiers.
- Validation result.
- Rejection reason when blocked.

## Required Tests

Live execution code is not done unless tests prove:

- Default mode is paper.
- Paper mode cannot access live execution adapters.
- Missing live credentials block execution.
- Disabled live flag blocks execution.
- Kill switch blocks execution.
- Limits block oversized orders.
- Failed exchange responses are persisted or surfaced safely.

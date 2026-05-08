# Execution Design

## Purpose

This document describes the future execution layer. It should keep paper trading and live trading aligned at the strategy boundary while keeping their records and side effects separate.

## Design Goals

- Paper trading works first and remains available.
- Live execution uses explicit safety gates.
- Recommendations are separate from orders.
- Execution adapters are testable without network access.
- Live side effects are impossible in paper mode.

## Conceptual Flow

```text
Prediction
  -> EVRecommendation
    -> PaperTrade
    -> ExecutionIntent
      -> OrderPreview
      -> LiveOrder
      -> LiveFill
      -> LivePosition
```

Current implementation stops at `PaperTrade`. Future live trading should add the execution side without changing paper-trading records into live records.

## Core Concepts

### `EVRecommendation`

Strategy output that says what the model believes has edge.

Responsibilities:

- Store model probability, market price, edge, EV, sizing suggestion, and reason.
- Link back to prediction and price snapshot.

Non-responsibilities:

- It is not an order.
- It should not store exchange execution state.

### `PaperTrade`

Simulated position created from a recommendation.

Responsibilities:

- Test strategy behavior without real execution.
- Support paper PnL and evaluation.
- Remain usable in every environment.

### `ExecutionIntent`

Future record representing an approved intent to trade.

Responsibilities:

- Link to recommendation.
- Capture requested side, size, price constraints, trading mode, and actor.
- Record validation status.
- Exist before any live order is placed.

### `ExecutionAdapter`

Interface for execution backends.

Expected methods:

```python
class ExecutionAdapter:
    def preview_order(self, intent): ...
    def place_order(self, intent): ...
    def cancel_order(self, order_id): ...
    def sync_positions(self): ...
```

Expected implementations:

- `PaperExecutionAdapter`
- `LiveExecutionAdapter`
- `ReadOnlyExecutionAdapter`

## Safety Rules

- Paper adapter cannot call live APIs.
- Live adapter cannot be constructed without live configuration and credentials.
- Order placement must run validation before side effects.
- Every live-intent action must be auditable.
- Paper and live records must be queryable separately.

## Implementation Sequence

1. Finish paper-trading workflow.
2. Add backtesting and replay metrics.
3. Add trading mode configuration.
4. Add execution intent and audit records.
5. Add paper execution adapter.
6. Add live safety gates and tests.
7. Add live adapter behind explicit configuration.
8. Add sandbox/testnet integration tests if available.

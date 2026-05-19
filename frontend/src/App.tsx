import { Fragment, useEffect, useMemo, useState } from "react";
import {
  DashboardMarketSummary,
  DashboardSummary,
  EvidenceReport,
  EvaluationSummary,
  HealthStatus,
  Opportunity,
  PaperRunnerDiagnostics,
  PaperRunnerRun,
  PaperTrade,
  ResolvedOutcome,
  WorkflowStatus,
  fetchDashboardSummary,
  fetchEvidenceReport,
  fetchHealth,
  fetchPaperRunnerDiagnostics,
  fetchPaperRunnerRuns,
  fetchPaperTrades,
  fetchResolvedOutcomes,
  runPaperWorkflow,
  runPublicPaperPass,
} from "./api";

const steps: Array<{ key: keyof WorkflowStatus; label: string }> = [
  { key: "has_price_snapshot", label: "Price" },
  { key: "has_parsed_market", label: "Parse" },
  { key: "has_forecast_snapshot", label: "Forecast" },
  { key: "has_prediction", label: "Model" },
  { key: "has_ev_recommendation", label: "EV" },
  { key: "has_paper_trade", label: "Paper" },
];

type RunMode = "demo" | "public";
type TradeFilter = "OPEN" | "ALL";
type ActiveView = "overview" | "markets" | "runs" | "trades" | "evidence" | "diagnostics";

type Filters = {
  modelVersion: string;
  source: string;
  nextAction: string;
  tradeStatus: TradeFilter;
  runMode: string;
  startDate: string;
  endDate: string;
};

const today = new Date();
const thirtyDaysAgo = new Date(today);
thirtyDaysAgo.setDate(today.getDate() - 30);

function toDateInput(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? "n/a" : `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "n/a" : value.toFixed(digits);
}

function formatSignedNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "n/a";
  return value > 0 ? `+${value.toFixed(digits)}` : value.toFixed(digits);
}

function formatMeasurement(value: number | null | undefined, unit: string | null | undefined): string {
  return value === null || value === undefined ? "n/a" : `${formatNumber(value, 2)}${unit ? ` ${unit}` : ""}`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "n/a";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatAction(action: string): string {
  return action
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function compactText(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function nestedRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function Pipeline({ status }: { status: WorkflowStatus }) {
  return (
    <div className="pipeline" aria-label={`Next action ${formatAction(status.next_action)}`}>
      {steps.map((step) => (
        <span className={status[step.key] ? "pipelineStep pipelineStepDone" : "pipelineStep"} key={step.key}>
          {step.label}
        </span>
      ))}
    </div>
  );
}

function StatusDot({ health }: { health: HealthStatus | null }) {
  return <span className={health?.status === "ok" ? "health ok" : "health"}>{health?.service ?? "API unavailable"}</span>;
}

function SafetyStrip() {
  return (
    <section className="safetyStrip" aria-label="Trading mode boundary">
      <span>Paper mode</span>
      <span>Live execution disabled</span>
      <span>No authenticated trading APIs</span>
    </section>
  );
}

function ViewTabs({ activeView, onChange }: { activeView: ActiveView; onChange: (view: ActiveView) => void }) {
  const tabs: Array<{ key: ActiveView; label: string }> = [
    { key: "overview", label: "Overview" },
    { key: "markets", label: "Markets" },
    { key: "runs", label: "Paper Runs" },
    { key: "trades", label: "Trades" },
    { key: "evidence", label: "Evidence" },
    { key: "diagnostics", label: "Diagnostics" },
  ];
  return (
    <nav className="viewTabs" aria-label="Dashboard sections">
      {tabs.map((tab) => (
        <button className={activeView === tab.key ? "active" : ""} key={tab.key} onClick={() => onChange(tab.key)} type="button">
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

function FilterBar({
  filters,
  sources,
  nextActions,
  onChange,
}: {
  filters: Filters;
  sources: string[];
  nextActions: string[];
  onChange: (filters: Filters) => void;
}) {
  return (
    <section className="filterBar">
      <label>
        <span>Model</span>
        <select value={filters.modelVersion} onChange={(event) => onChange({ ...filters, modelVersion: event.target.value })}>
          <option value="baseline_precip_v1">baseline_precip_v1</option>
          <option value="logistic_precip_v1">logistic_precip_v1</option>
        </select>
      </label>
      <label>
        <span>Source</span>
        <select value={filters.source} onChange={(event) => onChange({ ...filters, source: event.target.value })}>
          <option value="all">All sources</option>
          {sources.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Next action</span>
        <select value={filters.nextAction} onChange={(event) => onChange({ ...filters, nextAction: event.target.value })}>
          <option value="all">All actions</option>
          {nextActions.map((action) => (
            <option key={action} value={action}>
              {formatAction(action)}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Runs</span>
        <select value={filters.runMode} onChange={(event) => onChange({ ...filters, runMode: event.target.value })}>
          <option value="all">All runs</option>
          <option value="dry">Dry run</option>
          <option value="trade">Simulated trades</option>
        </select>
      </label>
      <label>
        <span>Start</span>
        <input type="date" value={filters.startDate} onChange={(event) => onChange({ ...filters, startDate: event.target.value })} />
      </label>
      <label>
        <span>End</span>
        <input type="date" value={filters.endDate} onChange={(event) => onChange({ ...filters, endDate: event.target.value })} />
      </label>
    </section>
  );
}

function StatCards({ summary, allTrades, outcomes, evidence }: { summary: DashboardSummary; allTrades: PaperTrade[]; outcomes: ResolvedOutcome[]; evidence: EvidenceReport | null }) {
  const openExposure = summary.open_paper_trades.reduce((total, trade) => total + trade.entry_price * trade.quantity, 0);
  const stats = [
    { label: "Markets", value: summary.recent_markets.length.toString() },
    { label: "Open Trades", value: summary.open_paper_trades.length.toString() },
    { label: "Open Exposure", value: formatNumber(openExposure, 2) },
    { label: "Evaluated", value: (evidence?.backtest.coverage_diagnostics.evaluated_prediction_count ?? summary.evaluation_summary.num_predictions).toString() },
    { label: "Unresolved", value: (evidence?.paper_trade_lifecycle.unresolved ?? 0).toString() },
  ];

  return (
    <section className="statsGrid" aria-label="Dashboard totals">
      {stats.map((stat) => (
        <div className="stat" key={stat.label}>
          <span>{stat.label}</span>
          <strong>{stat.value}</strong>
        </div>
      ))}
      <div className="stat">
        <span>Outcome Logs</span>
        <strong>{outcomes.length}</strong>
      </div>
      <div className="stat">
        <span>Total Trades</span>
        <strong>{allTrades.length}</strong>
      </div>
    </section>
  );
}

function RunConsole({
  mode,
  dryRun,
  maxTrades,
  quantity,
  minLiquidity,
  maxSpread,
  isRunning,
  actionMessage,
  onModeChange,
  onDryRunChange,
  onMaxTradesChange,
  onQuantityChange,
  onMinLiquidityChange,
  onMaxSpreadChange,
  onSubmit,
}: {
  mode: RunMode;
  dryRun: boolean;
  maxTrades: number;
  quantity: number;
  minLiquidity: number;
  maxSpread: number;
  isRunning: boolean;
  actionMessage: string | null;
  onModeChange: (mode: RunMode) => void;
  onDryRunChange: (value: boolean) => void;
  onMaxTradesChange: (value: number) => void;
  onQuantityChange: (value: number) => void;
  onMinLiquidityChange: (value: number) => void;
  onMaxSpreadChange: (value: number) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="runConsole">
      <div className="consoleMain">
        <div>
          <p className="eyebrow">Paper Execution</p>
          <h2>Run Console</h2>
        </div>
        <div className="segmented" role="group" aria-label="Run mode">
          <button className={mode === "demo" ? "active" : ""} onClick={() => onModeChange("demo")} type="button">
            Demo
          </button>
          <button className={mode === "public" ? "active" : ""} onClick={() => onModeChange("public")} type="button">
            Public
          </button>
        </div>
        <button className="primaryButton" disabled={isRunning} onClick={onSubmit} type="button">
          {isRunning ? "Running..." : mode === "demo" ? "Run Paper Demo" : dryRun ? "Run Public Dry Run" : "Run Public Paper Trade"}
        </button>
      </div>

      {mode === "public" ? (
        <div className="controlGrid">
          <label className="toggleControl">
            <input checked={dryRun} onChange={(event) => onDryRunChange(event.target.checked)} type="checkbox" />
            <span>Dry run</span>
          </label>
          <label>
            <span>Max trades</span>
            <input min="0" max="25" onChange={(event) => onMaxTradesChange(event.target.valueAsNumber)} type="number" value={maxTrades} />
          </label>
          <label>
            <span>Quantity</span>
            <input min="0.1" step="0.1" onChange={(event) => onQuantityChange(event.target.valueAsNumber)} type="number" value={quantity} />
          </label>
          <label>
            <span>Min liquidity</span>
            <input min="0" step="10" onChange={(event) => onMinLiquidityChange(event.target.valueAsNumber)} type="number" value={minLiquidity} />
          </label>
          <label>
            <span>Max spread</span>
            <input min="0" max="1" step="0.01" onChange={(event) => onMaxSpreadChange(event.target.valueAsNumber)} type="number" value={maxSpread} />
          </label>
        </div>
      ) : null}

      {actionMessage ? <div className="actionMessage">{actionMessage}</div> : null}
    </section>
  );
}

function MetricGrid({ metrics }: { metrics: Array<{ label: string; value: string }> }) {
  return (
    <div className="metricGrid">
      {metrics.map((metric) => (
        <div className="metric" key={metric.label}>
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
        </div>
      ))}
    </div>
  );
}

function EvaluationPanel({ evaluation }: { evaluation: EvaluationSummary }) {
  return (
    <section className="section evaluationSection">
      <div className="sectionHeader">
        <h2>Evidence Snapshot</h2>
        <span>
          {evaluation.model_version} / {evaluation.source}
        </span>
      </div>
      <MetricGrid
        metrics={[
          { label: "Predictions", value: evaluation.num_predictions.toString() },
          { label: "Win Rate", value: formatPercent(evaluation.win_rate) },
          { label: "Brier", value: formatNumber(evaluation.brier_score, 3) },
          { label: "Log Loss", value: formatNumber(evaluation.log_loss, 3) },
          { label: "Paper ROI", value: formatPercent(evaluation.paper_roi) },
          { label: "Net PnL", value: formatSignedNumber(evaluation.paper_total_pnl, 2) },
          { label: "Max Drawdown", value: formatNumber(evaluation.max_drawdown, 2) },
          { label: "Outcomes", value: evaluation.num_resolved_outcomes.toString() },
        ]}
      />
      {evaluation.calibration_buckets.length > 0 ? <CalibrationGrid buckets={evaluation.calibration_buckets} /> : null}
      {evaluation.sample_size_note ? <p className="note">{evaluation.sample_size_note}</p> : null}
    </section>
  );
}

function CalibrationGrid({ buckets }: { buckets: EvaluationSummary["calibration_buckets"] }) {
  return (
    <div className="calibrationGrid" aria-label="Calibration buckets">
      {buckets.map((bucket) => (
        <div className="calibrationBucket" key={`${bucket.lower_bound}-${bucket.upper_bound}`}>
          <span>
            {formatPercent(bucket.lower_bound)}-{formatPercent(bucket.upper_bound)}
          </span>
          <strong>{bucket.count}</strong>
          <small>
            Pred {formatPercent(bucket.average_predicted_probability)} / Obs {formatPercent(bucket.observed_yes_rate)}
          </small>
        </div>
      ))}
    </div>
  );
}

function MarketTable({ markets }: { markets: DashboardMarketSummary[] }) {
  const [expandedMarketId, setExpandedMarketId] = useState<number | null>(null);
  if (markets.length === 0) return <EmptyState text="No markets match the selected filters." />;

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Market</th>
            <th>Signal</th>
            <th>Pipeline</th>
            <th>Next</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {markets.map((market) => (
            <Fragment key={market.market_id}>
              <tr className="clickableRow" key={market.market_id} onClick={() => setExpandedMarketId(expandedMarketId === market.market_id ? null : market.market_id)}>
                <td>
                  <div className="marketCell">
                    <strong>{market.question}</strong>
                    <span>{market.parsed_target ?? `#${market.market_id}`}</span>
                    <div className="pillRow">
                      <span className={market.closed ? "statusPill muted" : "statusPill"}>{market.source}</span>
                      <span className={`priceStatus priceStatus-${market.price_status ?? "unknown"}`}>{market.price_status ?? "unknown"}</span>
                    </div>
                  </div>
                </td>
                <td>
                  <SignalGrid market={market} />
                </td>
                <td>
                  <Pipeline status={market.workflow_status} />
                </td>
                <td>{formatAction(market.workflow_status.next_action)}</td>
                <td>{formatDate(market.updated_at)}</td>
              </tr>
              {expandedMarketId === market.market_id ? (
                <tr className="detailRow" key={`${market.market_id}-detail`}>
                  <td colSpan={5}>
                    <MarketDetail market={market} />
                  </td>
                </tr>
              ) : null}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SignalGrid({ market }: { market: DashboardMarketSummary }) {
  return (
    <div className="signalGrid">
      <span>
        <b>Forecast</b> {formatMeasurement(market.forecast_precip_total, market.forecast_precip_unit)}
      </span>
      <span>
        <b>Model</b> {formatPercent(market.model_probability_yes)}
      </span>
      <span>
        <b>Price</b> {formatPercent(market.market_price_yes)}
      </span>
      <span>
        <b>Edge</b> {formatPercent(market.edge_yes)}
      </span>
      <span>
        <b>EV</b> {market.recommendation ?? "n/a"}
      </span>
      <span>
        <b>Trade</b> {market.paper_trade_status ?? "n/a"}
      </span>
    </div>
  );
}

function MarketDetail({ market }: { market: DashboardMarketSummary }) {
  return (
    <div className="detailPanel">
      <dl className="detailGrid">
        <div>
          <dt>Source market</dt>
          <dd>{market.source_market_id}</dd>
        </div>
        <div>
          <dt>Parsed target</dt>
          <dd>{market.parsed_target ?? "not parsed"}</dd>
        </div>
        <div>
          <dt>Forecast snapshot</dt>
          <dd>{market.latest_forecast_snapshot_id ?? "n/a"}</dd>
        </div>
        <div>
          <dt>Prediction</dt>
          <dd>{market.latest_prediction_id ?? "n/a"}</dd>
        </div>
        <div>
          <dt>Price snapshot</dt>
          <dd>{market.latest_price_snapshot_id ?? "n/a"}</dd>
        </div>
        <div>
          <dt>Recommendation</dt>
          <dd>{market.recommendation ?? "n/a"}</dd>
        </div>
      </dl>
      <div className="detailNotes">
        {market.source_error_label ? <span className="warningText">{market.source_error_label}</span> : null}
        {market.unsupported_reasons.length > 0 ? <span>Unsupported: {market.unsupported_reasons.map(formatAction).join(", ")}</span> : <span>No unsupported price reasons recorded.</span>}
      </div>
    </div>
  );
}

function OpportunityList({ opportunities }: { opportunities: Opportunity[] }) {
  if (opportunities.length === 0) return <EmptyState text="No paper-buy opportunities are currently stored." />;

  return (
    <div className="listStack">
      {opportunities.map((opportunity) => (
        <article className="record" key={`${opportunity.market_id}-${opportunity.prediction_id}`}>
          <div>
            <strong>{opportunity.recommendation}</strong>
            <p>{opportunity.question}</p>
          </div>
          <dl>
            <div>
              <dt>Model YES</dt>
              <dd>{formatPercent(opportunity.model_probability_yes)}</dd>
            </div>
            <div>
              <dt>Market YES</dt>
              <dd>{formatPercent(opportunity.market_price_yes)}</dd>
            </div>
            <div>
              <dt>Edge</dt>
              <dd>{formatPercent(opportunity.edge_yes)}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}

function TradeList({ trades, filter, onFilterChange }: { trades: PaperTrade[]; filter: TradeFilter; onFilterChange: (filter: TradeFilter) => void }) {
  const [expandedTradeId, setExpandedTradeId] = useState<number | null>(null);
  return (
    <section className="section">
      <div className="sectionHeader">
        <h2>Paper Trades</h2>
        <div className="segmented compactSegment">
          <button className={filter === "OPEN" ? "active" : ""} onClick={() => onFilterChange("OPEN")} type="button">
            Open
          </button>
          <button className={filter === "ALL" ? "active" : ""} onClick={() => onFilterChange("ALL")} type="button">
            All
          </button>
        </div>
      </div>
      {trades.length === 0 ? (
        <EmptyState text="No paper trades match this view." />
      ) : (
        <div className="tradeGrid">
          {trades.map((trade) => (
            <TradeCard expanded={expandedTradeId === trade.id} key={trade.id} onToggle={() => setExpandedTradeId(expandedTradeId === trade.id ? null : trade.id)} trade={trade} />
          ))}
        </div>
      )}
    </section>
  );
}

function TradeCard({ trade, expanded, onToggle }: { trade: PaperTrade; expanded: boolean; onToggle: () => void }) {
  const snapshot = trade.signal_snapshot_json ?? {};
  const reason = compactText(snapshot["recommendation_reason"]);
  return (
    <article className="tradeCard">
      <button className="cardButton" onClick={onToggle} type="button">
        <div className="tradeHeader">
          <div>
            <strong>
              {trade.side} #{trade.id}
            </strong>
            <span>Market #{trade.market_id}</span>
          </div>
          <span className={`tradeStatus tradeStatus-${trade.status.toLowerCase()}`}>{trade.status}</span>
        </div>
        <dl>
          <div>
            <dt>Entry</dt>
            <dd>{formatNumber(trade.entry_price)}</dd>
          </div>
          <div>
            <dt>Qty</dt>
            <dd>{formatNumber(trade.quantity, 1)}</dd>
          </div>
          <div>
            <dt>PnL</dt>
            <dd>{formatSignedNumber(trade.pnl)}</dd>
          </div>
          <div>
            <dt>Opened</dt>
            <dd>{formatDate(trade.entry_time)}</dd>
          </div>
        </dl>
      </button>
      {reason ? <p>{reason}</p> : null}
      {expanded ? <TradeSnapshot snapshot={snapshot} /> : null}
    </article>
  );
}

function TradeSnapshot({ snapshot }: { snapshot: Record<string, unknown> }) {
  const paperTrade = nestedRecord(snapshot["paper_trade"]);
  const parsedTarget = nestedRecord(snapshot["parsed_target"]);
  const forecast = nestedRecord(snapshot["forecast"]);
  const marketPrice = nestedRecord(snapshot["market_price"]);
  const model = nestedRecord(snapshot["model"]);
  const runner = nestedRecord(snapshot["runner_config"]);
  return (
    <div className="snapshotPanel">
      <dl className="detailGrid">
        <div>
          <dt>Quoted price</dt>
          <dd>{formatNumber(Number(paperTrade["quoted_entry_price"] ?? NaN) || null)}</dd>
        </div>
        <div>
          <dt>Fill price</dt>
          <dd>{formatNumber(Number(paperTrade["fill_entry_price"] ?? NaN) || null)}</dd>
        </div>
        <div>
          <dt>Slippage</dt>
          <dd>{formatPercent(Number(paperTrade["entry_slippage_rate"] ?? NaN) || null)}</dd>
        </div>
        <div>
          <dt>Liquidity</dt>
          <dd>{formatNumber(Number(marketPrice["liquidity"] ?? NaN) || null)}</dd>
        </div>
        <div>
          <dt>Spread</dt>
          <dd>{formatNumber(Number(marketPrice["spread"] ?? NaN) || null, 3)}</dd>
        </div>
        <div>
          <dt>Model YES</dt>
          <dd>{formatPercent(Number(model["p_yes"] ?? NaN) || null)}</dd>
        </div>
        <div>
          <dt>Forecast</dt>
          <dd>{formatMeasurement(Number(forecast["forecast_precip_total"] ?? NaN) || null, compactText(forecast["forecast_precip_unit"]))}</dd>
        </div>
        <div>
          <dt>Target</dt>
          <dd>{compactText(parsedTarget["location_name"]) ?? "n/a"}</dd>
        </div>
        <div>
          <dt>Runner cap</dt>
          <dd>{String(runner["max_trades"] ?? "n/a")}</dd>
        </div>
      </dl>
    </div>
  );
}

function OutcomeLog({ outcomes }: { outcomes: ResolvedOutcome[] }) {
  return (
    <section className="section">
      <div className="sectionHeader">
        <h2>Outcome Logs</h2>
        <span>{outcomes.length} records</span>
      </div>
      {outcomes.length === 0 ? (
        <EmptyState text="No resolved outcomes are currently stored." />
      ) : (
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Outcome</th>
                <th>Observed</th>
                <th>Source</th>
                <th>Resolved</th>
              </tr>
            </thead>
            <tbody>
              {outcomes.map((outcome) => (
                <tr key={outcome.id}>
                  <td>
                    <strong>
                      {outcome.actual_outcome} / Market #{outcome.market_id}
                    </strong>
                  </td>
                  <td>{formatMeasurement(outcome.actual_value, outcome.actual_unit)}</td>
                  <td>{outcome.resolution_source ?? "n/a"}</td>
                  <td>{formatDate(outcome.resolved_at ?? outcome.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function PaperRunnerRuns({ runs }: { runs: PaperRunnerRun[] }) {
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  if (runs.length === 0) return <EmptyState text="No public paper-runner history is currently stored." />;

  return (
    <div className="runnerGrid">
      {runs.map((run) => (
        <article className="runnerRun" key={run.id}>
          <button className="cardButton" onClick={() => setExpandedRunId(expandedRunId === run.id ? null : run.id)} type="button">
            <div className="runnerHeader">
              <div>
                <strong>Run #{run.id}</strong>
                <span>{run.dry_run ? "Dry run" : "Simulated trades enabled"}</span>
              </div>
              <span className={`runStatus runStatus-${run.status}`}>{run.status}</span>
            </div>
            <dl className="runnerMetrics">
              <div>
                <dt>Discovered</dt>
                <dd>{run.discovered}</dd>
              </div>
              <div>
                <dt>Processed</dt>
                <dd>{run.processed}</dd>
              </div>
              <div>
                <dt>Signals</dt>
                <dd>{run.recommendations_created}</dd>
              </div>
              <div>
                <dt>Trades</dt>
                <dd>{run.paper_trades_created}</dd>
              </div>
            </dl>
          </button>
          <RunDetail run={run} expanded={expandedRunId === run.id} />
        </article>
      ))}
    </div>
  );
}

function RunDetail({ run, expanded }: { run: PaperRunnerRun; expanded: boolean }) {
  const skipEntries = Object.entries(run.skipped).filter(([, count]) => count > 0);
  const config = run.config ?? {};
  return (
    <div className="runnerDetail">
      <span>
        {run.source} / {formatDate(run.started_at)}
      </span>
      <small>{skipEntries.length > 0 ? `Skips: ${skipEntries.map(([reason, count]) => `${formatAction(reason)} ${count}`).join(", ")}` : "No skip reasons recorded."}</small>
      {run.errors.length > 0 ? <small className="errorText">Errors: {run.errors.join("; ")}</small> : null}
      {expanded ? (
        <dl className="detailGrid compactDetail">
          <div>
            <dt>Actionable</dt>
            <dd>{run.actionable_recommendations ?? "n/a"}</dd>
          </div>
          <div>
            <dt>Expected trades</dt>
            <dd>{run.expected_paper_trades ?? "n/a"}</dd>
          </div>
          <div>
            <dt>Max trades</dt>
            <dd>{String(config["max_trades"] ?? "n/a")}</dd>
          </div>
          <div>
            <dt>Liquidity min</dt>
            <dd>{String(config["min_liquidity"] ?? "n/a")}</dd>
          </div>
          <div>
            <dt>Max spread</dt>
            <dd>{String(config["max_spread"] ?? "n/a")}</dd>
          </div>
          <div>
            <dt>Stale fallback</dt>
            <dd>{String(config["allow_stale_price_fallback"] ?? false)}</dd>
          </div>
        </dl>
      ) : null}
    </div>
  );
}

function EvidenceView({ evidence }: { evidence: EvidenceReport | null }) {
  if (!evidence) return <EmptyState text="Evidence report is not available for the selected window." />;
  return (
    <div className="evidenceStack">
      <section className="section">
        <div className="sectionHeader">
          <h2>Evidence Report</h2>
          <span>
            {evidence.start_date} to {evidence.end_date}
          </span>
        </div>
        <MetricGrid
          metrics={[
            { label: "Sample gate", value: evidence.sample_size_gate ?? "n/a" },
            { label: "Evaluated", value: evidence.backtest.coverage_diagnostics.evaluated_prediction_count.toString() },
            { label: "Outcomes", value: evidence.counts.resolved_outcomes.toString() },
            { label: "Open trades", value: evidence.paper_trade_lifecycle.open.toString() },
            { label: "Unresolved", value: evidence.paper_trade_lifecycle.unresolved.toString() },
            { label: "Past window", value: evidence.paper_trade_lifecycle.unresolved_past_target_window.toString() },
            { label: "Buy signals", value: evidence.paper_trade_lifecycle.recommended_buy_signals.toString() },
            { label: "Not traded", value: evidence.paper_trade_lifecycle.recommended_but_not_traded.toString() },
          ]}
        />
        {evidence.sample_size_note ? <p className="note">{evidence.sample_size_note}</p> : null}
        {evidence.interpretation_limits.length > 0 ? (
          <div className="limitList">
            {evidence.interpretation_limits.map((limit) => (
              <span key={limit}>{limit}</span>
            ))}
          </div>
        ) : null}
      </section>
      <section className="section">
        <div className="sectionHeader">
          <h2>Baseline Comparisons</h2>
          <span>Model vs controls</span>
        </div>
        <ComparisonTable evidence={evidence} />
      </section>
      <section className="section">
        <div className="sectionHeader">
          <h2>Calibration</h2>
          <span>{evidence.backtest.calibration_buckets.length} buckets</span>
        </div>
        {evidence.backtest.calibration_buckets.length > 0 ? <CalibrationGrid buckets={evidence.backtest.calibration_buckets} /> : <EmptyState text="No calibration buckets are available for this report." />}
      </section>
    </div>
  );
}

function ComparisonTable({ evidence }: { evidence: EvidenceReport }) {
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Comparison</th>
            <th>Predictions</th>
            <th>Brier</th>
            <th>Log loss</th>
            <th>Win rate</th>
          </tr>
        </thead>
        <tbody>
          {evidence.backtest.baseline_comparisons.map((comparison) => (
            <tr key={comparison.name}>
              <td>{formatAction(comparison.name)}</td>
              <td>{comparison.prediction_count}</td>
              <td>{formatNumber(comparison.brier_score, 3)}</td>
              <td>{formatNumber(comparison.log_loss, 3)}</td>
              <td>{formatPercent(comparison.win_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DiagnosticsView({ diagnostics }: { diagnostics: PaperRunnerDiagnostics | null }) {
  if (!diagnostics) return <EmptyState text="Paper-runner diagnostics are not available." />;
  return (
    <div className="diagnosticsGrid">
      <section className="section">
        <div className="sectionHeader">
          <h2>Runner Funnel</h2>
          <span>{diagnostics.run_count} runs</span>
        </div>
        <MetricGrid
          metrics={[
            { label: "Discovered", value: diagnostics.discovered.toString() },
            { label: "Processed", value: diagnostics.processed.toString() },
            { label: "Parsed", value: diagnostics.parsed.toString() },
            { label: "Forecasts", value: diagnostics.forecasts_created.toString() },
            { label: "Predictions", value: diagnostics.predictions_created.toString() },
            { label: "Recommendations", value: diagnostics.recommendations_created.toString() },
            { label: "Trades", value: diagnostics.paper_trades_created.toString() },
            { label: "Stale fallback", value: diagnostics.stale_price_fallbacks_used.toString() },
          ]}
        />
      </section>
      <section className="section">
        <div className="sectionHeader">
          <h2>Skip Reasons</h2>
          <span>{diagnostics.skip_reasons.length} categories</span>
        </div>
        <div className="reasonList">
          {diagnostics.skip_reasons.length === 0 ? <EmptyState text="No skip reasons recorded." /> : diagnostics.skip_reasons.map((reason) => (
            <div className="reasonRow" key={reason.reason}>
              <span>{reason.label}</span>
              <small>{reason.category}</small>
              <strong>{reason.count}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="section">
        <div className="sectionHeader">
          <h2>Price Diagnostics</h2>
          <span>{diagnostics.source ?? "all sources"}</span>
        </div>
        <div className="reasonList">
          {Object.entries(diagnostics.price_status_counts).map(([status, count]) => (
            <div className="reasonRow" key={status}>
              <span>{formatAction(status)}</span>
              <small>price status</small>
              <strong>{count}</strong>
            </div>
          ))}
          {diagnostics.unsupported_price_reasons.map((reason) => (
            <div className="reasonRow" key={reason.reason}>
              <span>{formatAction(reason.reason)}</span>
              <small>unsupported reason</small>
              <strong>{reason.count}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="section">
        <div className="sectionHeader">
          <h2>Recent Errors</h2>
          <span>{diagnostics.error_count} total</span>
        </div>
        <div className="reasonList">
          {diagnostics.recent_errors.length === 0 ? <EmptyState text="No recent runner errors recorded." /> : diagnostics.recent_errors.map((error) => (
            <div className="reasonRow errorReason" key={`${error.run_id}-${error.message}`}>
              <span>{error.message}</span>
              <small>Run #{error.run_id}</small>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="emptyState">{text}</div>;
}

const emptySummary: DashboardSummary = {
  recent_markets: [],
  opportunities: [],
  open_paper_trades: [],
  recent_paper_runs: [],
  evaluation_summary: {
    model_version: "baseline_precip_v1",
    source: "unavailable",
    status: "unavailable",
    num_predictions: 0,
    num_resolved_outcomes: 0,
    win_rate: null,
    brier_score: null,
    log_loss: null,
    paper_roi: null,
    paper_gross_pnl: null,
    paper_fee_cost: null,
    paper_slippage_cost: null,
    paper_total_pnl: null,
    max_drawdown: null,
    paper_settlement_note: null,
    sample_size_note: null,
    calibration_buckets: [],
  },
};

export function App() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [allTrades, setAllTrades] = useState<PaperTrade[]>([]);
  const [openTrades, setOpenTrades] = useState<PaperTrade[]>([]);
  const [outcomes, setOutcomes] = useState<ResolvedOutcome[]>([]);
  const [runnerRuns, setRunnerRuns] = useState<PaperRunnerRun[]>([]);
  const [diagnostics, setDiagnostics] = useState<PaperRunnerDiagnostics | null>(null);
  const [evidence, setEvidence] = useState<EvidenceReport | null>(null);
  const [loadedAt, setLoadedAt] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ActiveView>("overview");
  const [mode, setMode] = useState<RunMode>("demo");
  const [dryRun, setDryRun] = useState(true);
  const [maxTrades, setMaxTrades] = useState(1);
  const [quantity, setQuantity] = useState(1);
  const [minLiquidity, setMinLiquidity] = useState(100);
  const [maxSpread, setMaxSpread] = useState(0.15);
  const [filters, setFilters] = useState<Filters>({
    modelVersion: "baseline_precip_v1",
    source: "all",
    nextAction: "all",
    tradeStatus: "OPEN",
    runMode: "all",
    startDate: toDateInput(thirtyDaysAgo),
    endDate: toDateInput(today),
  });

  const visibleSummary = summary ?? emptySummary;
  const sources = useMemo(() => Array.from(new Set(visibleSummary.recent_markets.map((market) => market.source))).sort(), [visibleSummary.recent_markets]);
  const nextActions = useMemo(() => Array.from(new Set(visibleSummary.recent_markets.map((market) => market.workflow_status.next_action))).sort(), [visibleSummary.recent_markets]);
  const filteredMarkets = useMemo(
    () =>
      visibleSummary.recent_markets.filter((market) => {
        const sourceOk = filters.source === "all" || market.source === filters.source;
        const actionOk = filters.nextAction === "all" || market.workflow_status.next_action === filters.nextAction;
        return sourceOk && actionOk;
      }),
    [filters.nextAction, filters.source, visibleSummary.recent_markets],
  );
  const displayedTrades = filters.tradeStatus === "OPEN" ? openTrades : allTrades;
  const filteredRuns = useMemo(
    () =>
      runnerRuns.filter((run) => {
        if (filters.runMode === "dry") return run.dry_run;
        if (filters.runMode === "trade") return !run.dry_run;
        return true;
      }),
    [filters.runMode, runnerRuns],
  );
  const netPnl = useMemo(() => allTrades.reduce((total, trade) => total + (trade.pnl ?? 0), 0), [allTrades]);

  async function loadDashboard() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextHealth, nextSummary, nextAllTrades, nextOpenTrades, nextOutcomes, nextRuns, nextDiagnostics, nextEvidence] = await Promise.all([
        fetchHealth(),
        fetchDashboardSummary(),
        fetchPaperTrades(),
        fetchPaperTrades("OPEN"),
        fetchResolvedOutcomes(),
        fetchPaperRunnerRuns(),
        fetchPaperRunnerDiagnostics(),
        fetchEvidenceReport(filters.startDate, filters.endDate, filters.modelVersion),
      ]);
      setHealth(nextHealth);
      setSummary(nextSummary);
      setAllTrades(nextAllTrades);
      setOpenTrades(nextOpenTrades);
      setOutcomes(nextOutcomes);
      setRunnerRuns(nextRuns);
      setDiagnostics(nextDiagnostics);
      setEvidence(nextEvidence);
      setLoadedAt(new Date());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load dashboard");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, [filters.startDate, filters.endDate, filters.modelVersion]);

  async function runSelectedWorkflow() {
    setIsRunning(true);
    setActionMessage(null);
    try {
      if (mode === "demo") {
        const result = await runPaperWorkflow();
        await loadDashboard();
        setActionMessage(`${result.message} ${result.recommendation}${result.paper_trade_id ? ` / paper trade #${result.paper_trade_id}` : ""}`);
      } else {
        const result = await runPublicPaperPass({ dryRun, maxTrades, quantity, minLiquidity, maxSpread });
        await loadDashboard();
        setActionMessage(
          `Public run #${result.id} ${result.status}: actionable ${result.actionable_recommendations}, expected ${result.expected_paper_trades}, created ${result.paper_trades_created}.`,
        );
      }
    } catch (caught) {
      setActionMessage(caught instanceof Error ? caught.message : "Unable to run paper workflow");
    } finally {
      setIsRunning(false);
    }
  }

  if (isLoading && summary === null) return <div className="pageState">Loading dashboard...</div>;

  if (error !== null && summary === null) {
    return (
      <div className="pageState">
        <strong>Dashboard unavailable</strong>
        <span>{error}</span>
      </div>
    );
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">WeatherEdge AI</p>
          <h1>Paper Trading Workspace</h1>
        </div>
        <div className="topbarMeta">
          <StatusDot health={health} />
          <button onClick={() => void loadDashboard()} type="button">
            Refresh
          </button>
        </div>
      </header>

      <SafetyStrip />

      <RunConsole
        actionMessage={actionMessage}
        dryRun={dryRun}
        isRunning={isRunning}
        maxSpread={maxSpread}
        maxTrades={maxTrades}
        minLiquidity={minLiquidity}
        mode={mode}
        onDryRunChange={setDryRun}
        onMaxSpreadChange={(value) => setMaxSpread(Number.isFinite(value) ? value : 0.15)}
        onMaxTradesChange={(value) => setMaxTrades(Number.isFinite(value) ? value : 0)}
        onMinLiquidityChange={(value) => setMinLiquidity(Number.isFinite(value) ? value : 0)}
        onModeChange={setMode}
        onQuantityChange={(value) => setQuantity(Number.isFinite(value) ? value : 1)}
        onSubmit={() => void runSelectedWorkflow()}
        quantity={quantity}
      />

      <ViewTabs activeView={activeView} onChange={setActiveView} />
      <FilterBar filters={filters} nextActions={nextActions} onChange={setFilters} sources={sources} />

      {activeView === "overview" ? (
        <>
          <StatCards allTrades={allTrades} evidence={evidence} outcomes={outcomes} summary={visibleSummary} />
          <div className="split overviewSplit">
            <EvaluationPanel evaluation={visibleSummary.evaluation_summary} />
            <section className="section pnlPanel">
              <div className="sectionHeader">
                <h2>Paper Ledger</h2>
                <span>Loaded {loadedAt.toLocaleTimeString()}</span>
              </div>
              <div className="ledgerBody">
                <div>
                  <span>Open trades</span>
                  <strong>{openTrades.length}</strong>
                </div>
                <div>
                  <span>All-trade PnL</span>
                  <strong>{formatSignedNumber(netPnl)}</strong>
                </div>
                <div>
                  <span>Resolved outcomes</span>
                  <strong>{outcomes.length}</strong>
                </div>
              </div>
            </section>
          </div>
          <section className="section">
            <div className="sectionHeader">
              <h2>Market Workflow</h2>
              <span>Latest signals</span>
            </div>
            <MarketTable markets={filteredMarkets} />
          </section>
        </>
      ) : null}

      {activeView === "markets" ? (
        <section className="section">
          <div className="sectionHeader">
            <h2>Market Workflow</h2>
            <span>{filteredMarkets.length} markets</span>
          </div>
          <MarketTable markets={filteredMarkets} />
        </section>
      ) : null}

      {activeView === "runs" ? (
        <section className="section paperRunsSection">
          <div className="sectionHeader">
            <h2>Public Paper Runs</h2>
            <span>{filteredRuns.length} runs</span>
          </div>
          <PaperRunnerRuns runs={filteredRuns} />
        </section>
      ) : null}

      {activeView === "trades" ? (
        <div className="split">
          <section className="section">
            <div className="sectionHeader">
              <h2>Paper Opportunities</h2>
            </div>
            <OpportunityList opportunities={visibleSummary.opportunities} />
          </section>
          <TradeList filter={filters.tradeStatus} onFilterChange={(tradeStatus) => setFilters({ ...filters, tradeStatus })} trades={displayedTrades} />
        </div>
      ) : null}

      {activeView === "evidence" ? <EvidenceView evidence={evidence} /> : null}

      {activeView === "diagnostics" ? <DiagnosticsView diagnostics={diagnostics} /> : null}

      {activeView === "trades" || activeView === "evidence" ? <OutcomeLog outcomes={outcomes} /> : null}

      {error !== null ? <div className="floatingError">{error}</div> : null}
    </main>
  );
}

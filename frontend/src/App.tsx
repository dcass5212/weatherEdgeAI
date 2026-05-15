import { useEffect, useMemo, useState } from "react";
import {
  DashboardMarketSummary,
  DashboardSummary,
  EvaluationSummary,
  HealthStatus,
  Opportunity,
  PaperRunnerRun,
  PaperTrade,
  ResolvedOutcome,
  WorkflowStatus,
  fetchDashboardSummary,
  fetchHealth,
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

function StatCards({ summary, allTrades, outcomes }: { summary: DashboardSummary; allTrades: PaperTrade[]; outcomes: ResolvedOutcome[] }) {
  const openExposure = summary.open_paper_trades.reduce((total, trade) => total + trade.entry_price * trade.quantity, 0);
  const stats = [
    { label: "Markets", value: summary.recent_markets.length.toString() },
    { label: "Open Trades", value: summary.open_paper_trades.length.toString() },
    { label: "Open Exposure", value: formatNumber(openExposure, 2) },
    { label: "Outcome Logs", value: outcomes.length.toString() },
    { label: "Total Trades", value: allTrades.length.toString() },
  ];

  return (
    <section className="statsGrid" aria-label="Dashboard totals">
      {stats.map((stat) => (
        <div className="stat" key={stat.label}>
          <span>{stat.label}</span>
          <strong>{stat.value}</strong>
        </div>
      ))}
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

function EvaluationPanel({ evaluation }: { evaluation: EvaluationSummary }) {
  const metrics = [
    { label: "Predictions", value: evaluation.num_predictions.toString() },
    { label: "Win Rate", value: formatPercent(evaluation.win_rate) },
    { label: "Brier", value: formatNumber(evaluation.brier_score, 3) },
    { label: "Log Loss", value: formatNumber(evaluation.log_loss, 3) },
    { label: "Paper ROI", value: formatPercent(evaluation.paper_roi) },
    { label: "Net PnL", value: formatSignedNumber(evaluation.paper_total_pnl, 2) },
    { label: "Max Drawdown", value: formatNumber(evaluation.max_drawdown, 2) },
    { label: "Outcomes", value: evaluation.num_resolved_outcomes.toString() },
  ];

  return (
    <section className="section evaluationSection">
      <div className="sectionHeader">
        <h2>Evidence</h2>
        <span>
          {evaluation.model_version} / {evaluation.source}
        </span>
      </div>
      <div className="metricGrid">
        {metrics.map((metric) => (
          <div className="metric" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </div>
        ))}
      </div>
      {evaluation.calibration_buckets.length > 0 ? (
        <div className="calibrationGrid" aria-label="Calibration buckets">
          {evaluation.calibration_buckets.map((bucket) => (
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
      ) : null}
      {evaluation.sample_size_note ? <p className="note">{evaluation.sample_size_note}</p> : null}
    </section>
  );
}

function MarketTable({ markets }: { markets: DashboardMarketSummary[] }) {
  if (markets.length === 0) return <EmptyState text="No markets have been discovered yet." />;

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
            <tr key={market.market_id}>
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
              </td>
              <td>
                <Pipeline status={market.workflow_status} />
              </td>
              <td>{formatAction(market.workflow_status.next_action)}</td>
              <td>{formatDate(market.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
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
          {trades.map((trade) => {
            const snapshot = trade.signal_snapshot_json ?? {};
            const reason = compactText(snapshot["recommendation_reason"]);
            return (
              <article className="tradeCard" key={trade.id}>
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
                {reason ? <p>{reason}</p> : null}
              </article>
            );
          })}
        </div>
      )}
    </section>
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
  if (runs.length === 0) return <EmptyState text="No public paper-runner history is currently stored." />;

  return (
    <div className="runnerGrid">
      {runs.map((run) => {
        const skipEntries = Object.entries(run.skipped).filter(([, count]) => count > 0);
        return (
          <article className="runnerRun" key={run.id}>
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
            <div className="runnerDetail">
              <span>
                {run.source} / {formatDate(run.started_at)}
              </span>
              <small>{skipEntries.length > 0 ? `Skips: ${skipEntries.map(([reason, count]) => `${formatAction(reason)} ${count}`).join(", ")}` : "No skip reasons recorded."}</small>
              {run.errors.length > 0 ? <small className="errorText">Errors: {run.errors.join("; ")}</small> : null}
            </div>
          </article>
        );
      })}
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
  const [loadedAt, setLoadedAt] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [mode, setMode] = useState<RunMode>("demo");
  const [dryRun, setDryRun] = useState(true);
  const [maxTrades, setMaxTrades] = useState(1);
  const [quantity, setQuantity] = useState(1);
  const [minLiquidity, setMinLiquidity] = useState(100);
  const [maxSpread, setMaxSpread] = useState(0.15);
  const [tradeFilter, setTradeFilter] = useState<TradeFilter>("OPEN");

  const visibleSummary = summary ?? emptySummary;
  const displayedTrades = tradeFilter === "OPEN" ? openTrades : allTrades;
  const netPnl = useMemo(() => allTrades.reduce((total, trade) => total + (trade.pnl ?? 0), 0), [allTrades]);

  async function loadDashboard() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextHealth, nextSummary, nextAllTrades, nextOpenTrades, nextOutcomes] = await Promise.all([
        fetchHealth(),
        fetchDashboardSummary(),
        fetchPaperTrades(),
        fetchPaperTrades("OPEN"),
        fetchResolvedOutcomes(),
      ]);
      setHealth(nextHealth);
      setSummary(nextSummary);
      setAllTrades(nextAllTrades);
      setOpenTrades(nextOpenTrades);
      setOutcomes(nextOutcomes);
      setLoadedAt(new Date());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load dashboard");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

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

      <StatCards allTrades={allTrades} outcomes={outcomes} summary={visibleSummary} />

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

      <section className="section paperRunsSection">
        <div className="sectionHeader">
          <h2>Public Paper Runs</h2>
          <span>Recent runner history</span>
        </div>
        <PaperRunnerRuns runs={visibleSummary.recent_paper_runs} />
      </section>

      <section className="section">
        <div className="sectionHeader">
          <h2>Market Workflow</h2>
          <span>Latest signals</span>
        </div>
        <MarketTable markets={visibleSummary.recent_markets} />
      </section>

      <div className="split">
        <section className="section">
          <div className="sectionHeader">
            <h2>Paper Opportunities</h2>
          </div>
          <OpportunityList opportunities={visibleSummary.opportunities} />
        </section>
        <TradeList filter={tradeFilter} onFilterChange={setTradeFilter} trades={displayedTrades} />
      </div>

      <OutcomeLog outcomes={outcomes} />
    </main>
  );
}

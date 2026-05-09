import { useEffect, useMemo, useState } from "react";
import {
  DashboardMarketSummary,
  DashboardSummary,
  EvaluationSummary,
  HealthStatus,
  Opportunity,
  PaperTrade,
  WorkflowStatus,
  fetchDashboardSummary,
  fetchHealth,
  runPaperWorkflow,
} from "./api";

const steps: Array<{ key: keyof WorkflowStatus; label: string }> = [
  { key: "has_price_snapshot", label: "Price" },
  { key: "has_parsed_market", label: "Parse" },
  { key: "has_forecast_snapshot", label: "Forecast" },
  { key: "has_prediction", label: "Model" },
  { key: "has_ev_recommendation", label: "EV" },
  { key: "has_paper_trade", label: "Paper" },
];

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return value.toFixed(digits);
}

function formatSignedNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return value > 0 ? `+${value.toFixed(digits)}` : value.toFixed(digits);
}

function formatMeasurement(value: number | null | undefined, unit: string | null | undefined): string {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${formatNumber(value, 2)}${unit ? ` ${unit}` : ""}`;
}

function formatDate(value: string): string {
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

function formatReason(reason: string): string {
  return reason
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function Pipeline({ status }: { status: WorkflowStatus }) {
  return (
    <div className="pipeline" aria-label={`Next action ${formatAction(status.next_action)}`}>
      {steps.map((step) => (
        <span
          className={status[step.key] ? "pipelineStep pipelineStepDone" : "pipelineStep"}
          key={step.key}
          title={step.label}
        >
          {step.label}
        </span>
      ))}
    </div>
  );
}

function StatCards({ summary }: { summary: DashboardSummary }) {
  const stats = useMemo(() => {
    const completed = summary.recent_markets.filter(
      (market) => market.workflow_status.next_action === "monitor_paper_trade",
    ).length;
    return [
      { label: "Markets", value: summary.recent_markets.length.toString() },
      { label: "Paper Opportunities", value: summary.opportunities.length.toString() },
      { label: "Open Paper Trades", value: summary.open_paper_trades.length.toString() },
      { label: "Monitoring", value: completed.toString() },
    ];
  }, [summary]);

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

function EvaluationPanel({ evaluation }: { evaluation: EvaluationSummary }) {
  const metrics = [
    { label: "Predictions", value: evaluation.num_predictions.toString() },
    { label: "Win Rate", value: formatPercent(evaluation.win_rate) },
    { label: "Brier", value: formatNumber(evaluation.brier_score, 3) },
    { label: "Log Loss", value: formatNumber(evaluation.log_loss, 3) },
    { label: "Paper ROI", value: formatPercent(evaluation.paper_roi) },
    { label: "Paper PnL", value: formatSignedNumber(evaluation.paper_total_pnl, 2) },
    { label: "Max Drawdown", value: formatNumber(evaluation.max_drawdown, 2) },
    { label: "Outcomes", value: evaluation.num_resolved_outcomes.toString() },
  ];

  return (
    <section className="section evaluationSection">
      <div className="sectionHeader">
        <h2>Backtest & Calibration</h2>
        <span>
          {evaluation.model_version} / {evaluation.source}
        </span>
      </div>
      <div className="evaluationBody">
        <div className="metricGrid">
          {metrics.map((metric) => (
            <div className="metric" key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          ))}
        </div>
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
        {evaluation.sample_size_note ? <p className="note">{evaluation.sample_size_note}</p> : null}
      </div>
    </section>
  );
}

function MarketTable({ markets }: { markets: DashboardMarketSummary[] }) {
  if (markets.length === 0) {
    return <EmptyState text="No markets have been discovered yet." />;
  }

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Market</th>
            <th>Source</th>
            <th>Latest Signal</th>
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
                </div>
              </td>
              <td>
                <div className="sourceCell">
                  <span className={market.closed ? "statusPill muted" : "statusPill"}>{market.source}</span>
                  <span className={`priceStatus priceStatus-${market.price_status ?? "unknown"}`}>
                    {market.price_status ?? "unknown"}
                  </span>
                  {market.has_public_source_error ? <span className="sourceWarning">source error</span> : null}
                  {market.unsupported_reasons.length > 0 ? (
                    <small>{market.unsupported_reasons.map(formatReason).join(", ")}</small>
                  ) : null}
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
  if (opportunities.length === 0) {
    return <EmptyState text="No paper-buy opportunities are currently stored." />;
  }

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

function TradeList({ trades }: { trades: PaperTrade[] }) {
  if (trades.length === 0) {
    return <EmptyState text="No open paper trades are currently stored." />;
  }

  return (
    <div className="listStack">
      {trades.map((trade) => (
        <article className="record compact" key={trade.id}>
          <div>
            <strong>
              {trade.side} #{trade.id}
            </strong>
            <p>Market #{trade.market_id}</p>
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
              <dt>Status</dt>
              <dd>{trade.status}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="emptyState">{text}</div>;
}

function AppShell({
  summary,
  health,
  loadedAt,
  onRefresh,
  onRunPaperWorkflow,
  isRunningWorkflow,
  actionMessage,
}: {
  summary: DashboardSummary;
  health: HealthStatus | null;
  loadedAt: Date;
  onRefresh: () => void;
  onRunPaperWorkflow: () => void;
  isRunningWorkflow: boolean;
  actionMessage: string | null;
}) {
  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">WeatherEdge AI</p>
          <h1>Paper Trading Research Dashboard</h1>
        </div>
        <div className="topbarMeta">
          <span className={health?.status === "ok" ? "health ok" : "health"}>{health?.service ?? "API unavailable"}</span>
          <button disabled={isRunningWorkflow} onClick={onRunPaperWorkflow} type="button">
            {isRunningWorkflow ? "Running..." : "Run Paper Demo"}
          </button>
          <button onClick={onRefresh} type="button">
            Refresh
          </button>
        </div>
      </header>
      {actionMessage ? <div className="actionMessage">{actionMessage}</div> : null}

      <StatCards summary={summary} />
      <EvaluationPanel evaluation={summary.evaluation_summary} />

      <section className="section">
        <div className="sectionHeader">
          <h2>Market Workflow</h2>
          <span>Loaded {loadedAt.toLocaleTimeString()}</span>
        </div>
        <MarketTable markets={summary.recent_markets} />
      </section>

      <div className="split">
        <section className="section">
          <div className="sectionHeader">
            <h2>Paper Opportunities</h2>
          </div>
          <OpportunityList opportunities={summary.opportunities} />
        </section>

        <section className="section">
          <div className="sectionHeader">
            <h2>Open Paper Trades</h2>
          </div>
          <TradeList trades={summary.open_paper_trades} />
        </section>
      </div>
    </main>
  );
}

export function App() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loadedAt, setLoadedAt] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunningWorkflow, setIsRunningWorkflow] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  async function loadDashboard() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextHealth, nextSummary] = await Promise.all([fetchHealth(), fetchDashboardSummary()]);
      setHealth(nextHealth);
      setSummary(nextSummary);
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

  async function runDemoWorkflow() {
    setIsRunningWorkflow(true);
    setActionMessage(null);
    try {
      const result = await runPaperWorkflow();
      await loadDashboard();
      setActionMessage(
        `${result.message} ${result.recommendation}${result.paper_trade_id ? ` / paper trade #${result.paper_trade_id}` : ""}`,
      );
    } catch (caught) {
      setActionMessage(caught instanceof Error ? caught.message : "Unable to run paper demo workflow");
    } finally {
      setIsRunningWorkflow(false);
    }
  }

  if (isLoading && summary === null) {
    return <div className="pageState">Loading dashboard...</div>;
  }

  if (error !== null && summary === null) {
    return (
      <div className="pageState">
        <strong>Dashboard unavailable</strong>
        <span>{error}</span>
      </div>
    );
  }

  return (
    <AppShell
      summary={
        summary ?? {
          recent_markets: [],
          opportunities: [],
          open_paper_trades: [],
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
            paper_total_pnl: null,
            max_drawdown: null,
            sample_size_note: null,
            calibration_buckets: [],
          },
        }
      }
      health={health}
      loadedAt={loadedAt}
      onRefresh={() => void loadDashboard()}
      onRunPaperWorkflow={() => void runDemoWorkflow()}
      isRunningWorkflow={isRunningWorkflow}
      actionMessage={actionMessage}
    />
  );
}

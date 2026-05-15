/*
 * API client for the read-only portfolio dashboard.
 * It consumes FastAPI inspection endpoints plus an explicit paper-only demo
 * workflow action. It does not trigger live execution.
 */

export type WorkflowStatus = {
  has_price_snapshot: boolean;
  has_parsed_market: boolean;
  has_forecast_snapshot: boolean;
  has_prediction: boolean;
  has_ev_recommendation: boolean;
  has_paper_trade: boolean;
  next_action: string;
};

export type DashboardMarketSummary = {
  market_id: number;
  question: string;
  source: string;
  source_market_id: string;
  price_status: string | null;
  unsupported_reasons: string[];
  has_public_source_error: boolean;
  source_error_label: string | null;
  active: boolean;
  closed: boolean;
  latest_price_snapshot_id: number | null;
  latest_parsed_market_id: number | null;
  latest_forecast_snapshot_id: number | null;
  latest_prediction_id: number | null;
  latest_ev_recommendation_id: number | null;
  latest_paper_trade_id: number | null;
  parsed_target: string | null;
  forecast_precip_total: number | null;
  forecast_precip_unit: string | null;
  model_probability_yes: number | null;
  market_price_yes: number | null;
  edge_yes: number | null;
  recommendation: string | null;
  paper_trade_status: string | null;
  workflow_status: WorkflowStatus;
  updated_at: string;
};

export type Opportunity = {
  market_id: number;
  prediction_id: number;
  price_snapshot_id: number | null;
  question: string;
  model_probability_yes: number;
  market_price_yes: number | null;
  edge_yes: number | null;
  recommendation: string;
  created_at: string;
};

export type PaperTrade = {
  id: number;
  market_id: number;
  recommendation_id: number | null;
  side: string;
  entry_price: number;
  quantity: number;
  entry_time: string;
  exit_price: number | null;
  exit_time: string | null;
  pnl: number | null;
  status: string;
  signal_snapshot_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type ResolvedOutcome = {
  id: number;
  market_id: number;
  actual_outcome: "YES" | "NO";
  actual_value: number | null;
  actual_unit: string | null;
  resolution_source: string | null;
  resolved_at: string | null;
  raw_json: Record<string, unknown> | null;
  created_at: string;
};

export type CalibrationBucket = {
  lower_bound: number;
  upper_bound: number;
  count: number;
  average_predicted_probability: number | null;
  observed_yes_rate: number | null;
  calibration_gap: number | null;
};

export type EvaluationSummary = {
  model_version: string;
  source: string;
  status: string;
  num_predictions: number;
  num_resolved_outcomes: number;
  win_rate: number | null;
  brier_score: number | null;
  log_loss: number | null;
  paper_roi: number | null;
  paper_gross_pnl: number | null;
  paper_fee_cost: number | null;
  paper_slippage_cost: number | null;
  paper_total_pnl: number | null;
  max_drawdown: number | null;
  paper_settlement_note: string | null;
  sample_size_note: string | null;
  calibration_buckets: CalibrationBucket[];
};

export type PaperRunnerRun = {
  id: number;
  status: string;
  source: string;
  started_at: string;
  completed_at: string | null;
  dry_run: boolean;
  discovered: number;
  processed: number;
  parsed: number;
  forecasts_created: number;
  predictions_created: number;
  recommendations_created: number;
  paper_trades_created: number;
  skipped: Record<string, number>;
  errors: string[];
};

export type DashboardSummary = {
  recent_markets: DashboardMarketSummary[];
  opportunities: Opportunity[];
  open_paper_trades: PaperTrade[];
  evaluation_summary: EvaluationSummary;
  recent_paper_runs: PaperRunnerRun[];
};

export type HealthStatus = {
  status: string;
  service: string;
};

export type PaperWorkflowResult = {
  market_id: number;
  parsed_market_id: number;
  forecast_snapshot_id: number;
  prediction_id: number;
  recommendation_id: number;
  paper_trade_id: number | null;
  recommendation: string;
  steps_completed: string[];
  message: string;
};

export type PaperRunnerRunResult = PaperRunnerRun & {
  config: Record<string, unknown>;
  created: number;
  updated: number;
  price_snapshots_created: number;
  actionable_recommendations: number;
  expected_paper_trades: number;
  report: Record<string, unknown> | null;
};

async function readJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return readJson<DashboardSummary>("/dashboard/summary");
}

export async function fetchHealth(): Promise<HealthStatus> {
  return readJson<HealthStatus>("/health");
}

export async function fetchPaperTrades(status?: string): Promise<PaperTrade[]> {
  const query = status ? `?status=${encodeURIComponent(status)}&limit=100` : "?limit=100";
  return readJson<PaperTrade[]>(`/paper-trades${query}`);
}

export async function fetchResolvedOutcomes(): Promise<ResolvedOutcome[]> {
  return readJson<ResolvedOutcome[]>("/backtests/resolved-outcomes?limit=100");
}

export async function runPaperWorkflow(): Promise<PaperWorkflowResult> {
  return readJson<PaperWorkflowResult>("/demo/paper-workflow", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quantity: 10 }),
  });
}

export async function runPublicPaperDryRun(): Promise<PaperRunnerRunResult> {
  return readJson<PaperRunnerRunResult>("/paper-runner/run-once", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dry_run: true,
      max_trades: 1,
      quantity: 1,
      min_liquidity: 100,
      max_spread: 0.15,
    }),
  });
}

export type PublicPaperRunOptions = {
  dryRun: boolean;
  maxTrades: number;
  quantity: number;
  minLiquidity: number;
  maxSpread: number;
};

export async function runPublicPaperPass(options: PublicPaperRunOptions): Promise<PaperRunnerRunResult> {
  return readJson<PaperRunnerRunResult>("/paper-runner/run-once", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dry_run: options.dryRun,
      max_trades: options.maxTrades,
      quantity: options.quantity,
      min_liquidity: options.minLiquidity,
      max_spread: options.maxSpread,
    }),
  });
}

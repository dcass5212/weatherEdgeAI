"""Initial schema for WeatherEdge AI persistence.

Revision ID: 20260507_0001
Revises:
Create Date: 2026-05-07 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_market_id", sa.String(length=255), nullable=False),
        sa.Column("condition_id", sa.String(length=255), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_source", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_market_id", name="uq_market_source_source_market_id"),
    )
    op.create_index(op.f("ix_markets_active"), "markets", ["active"], unique=False)
    op.create_index(op.f("ix_markets_category"), "markets", ["category"], unique=False)
    op.create_index(op.f("ix_markets_closed"), "markets", ["closed"], unique=False)
    op.create_index(op.f("ix_markets_condition_id"), "markets", ["condition_id"], unique=False)
    op.create_index(op.f("ix_markets_id"), "markets", ["id"], unique=False)
    op.create_index(op.f("ix_markets_source"), "markets", ["source"], unique=False)
    op.create_index(op.f("ix_markets_source_market_id"), "markets", ["source_market_id"], unique=False)

    op.create_table(
        "market_price_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("yes_price", sa.Float(), nullable=True),
        sa.Column("no_price", sa.Float(), nullable=True),
        sa.Column("best_bid_yes", sa.Float(), nullable=True),
        sa.Column("best_ask_yes", sa.Float(), nullable=True),
        sa.Column("best_bid_no", sa.Float(), nullable=True),
        sa.Column("best_ask_no", sa.Float(), nullable=True),
        sa.Column("spread", sa.Float(), nullable=True),
        sa.Column("liquidity", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_market_price_snapshots_id"), "market_price_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_market_price_snapshots_market_id"), "market_price_snapshots", ["market_id"], unique=False)
    op.create_index(op.f("ix_market_price_snapshots_timestamp"), "market_price_snapshots", ["timestamp"], unique=False)

    op.create_table(
        "parsed_markets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("location_name", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("metric", sa.String(length=100), nullable=False),
        sa.Column("operator", sa.String(length=10), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("threshold_unit", sa.String(length=50), nullable=False),
        sa.Column("target_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_confidence", sa.Float(), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("raw_parse_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("threshold_value > 0", name="ck_parsed_market_threshold_positive"),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parsed_markets_id"), "parsed_markets", ["id"], unique=False)
    op.create_index(op.f("ix_parsed_markets_market_id"), "parsed_markets", ["market_id"], unique=False)

    op.create_table(
        "resolved_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("actual_outcome", sa.String(length=50), nullable=False),
        sa.Column("actual_value", sa.Float(), nullable=True),
        sa.Column("actual_unit", sa.String(length=50), nullable=True),
        sa.Column("resolution_source", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resolved_outcomes_id"), "resolved_outcomes", ["id"], unique=False)
    op.create_index(op.f("ix_resolved_outcomes_market_id"), "resolved_outcomes", ["market_id"], unique=False)

    op.create_table(
        "weather_forecast_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parsed_market_id", sa.Integer(), nullable=False),
        sa.Column("forecast_source", sa.String(length=100), nullable=False),
        sa.Column("forecast_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("forecast_precip_total", sa.Float(), nullable=True),
        sa.Column("forecast_precip_unit", sa.String(length=50), nullable=True),
        sa.Column("forecast_temp_max", sa.Float(), nullable=True),
        sa.Column("forecast_temp_min", sa.Float(), nullable=True),
        sa.Column("forecast_temp_unit", sa.String(length=50), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parsed_market_id"], ["parsed_markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_weather_forecast_snapshots_id"), "weather_forecast_snapshots", ["id"], unique=False)
    op.create_index(
        op.f("ix_weather_forecast_snapshots_parsed_market_id"),
        "weather_forecast_snapshots",
        ["parsed_market_id"],
        unique=False,
    )

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("parsed_market_id", sa.Integer(), nullable=True),
        sa.Column("forecast_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("p_yes", sa.Float(), nullable=False),
        sa.Column("p_no", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(length=50), nullable=True),
        sa.Column("features_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("p_no >= 0 AND p_no <= 1", name="ck_prediction_p_no_probability"),
        sa.CheckConstraint("p_yes >= 0 AND p_yes <= 1", name="ck_prediction_p_yes_probability"),
        sa.ForeignKeyConstraint(["forecast_snapshot_id"], ["weather_forecast_snapshots.id"]),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["parsed_market_id"], ["parsed_markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_predictions_forecast_snapshot_id"), "predictions", ["forecast_snapshot_id"], unique=False)
    op.create_index(op.f("ix_predictions_id"), "predictions", ["id"], unique=False)
    op.create_index(op.f("ix_predictions_market_id"), "predictions", ["market_id"], unique=False)
    op.create_index(op.f("ix_predictions_parsed_market_id"), "predictions", ["parsed_market_id"], unique=False)

    op.create_table(
        "ev_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prediction_id", sa.Integer(), nullable=False),
        sa.Column("price_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("market_price_yes", sa.Float(), nullable=True),
        sa.Column("market_price_no", sa.Float(), nullable=True),
        sa.Column("edge_yes", sa.Float(), nullable=True),
        sa.Column("edge_no", sa.Float(), nullable=True),
        sa.Column("ev_yes", sa.Float(), nullable=True),
        sa.Column("ev_no", sa.Float(), nullable=True),
        sa.Column("recommendation", sa.String(length=50), nullable=False),
        sa.Column("paper_position_size", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"]),
        sa.ForeignKeyConstraint(["price_snapshot_id"], ["market_price_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ev_recommendations_id"), "ev_recommendations", ["id"], unique=False)
    op.create_index(op.f("ix_ev_recommendations_prediction_id"), "ev_recommendations", ["prediction_id"], unique=False)
    op.create_index(
        op.f("ix_ev_recommendations_price_snapshot_id"), "ev_recommendations", ["price_snapshot_id"], unique=False
    )

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("entry_price >= 0 AND entry_price <= 1", name="ck_paper_trade_entry_price_probability"),
        sa.CheckConstraint("quantity > 0", name="ck_paper_trade_quantity_positive"),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["ev_recommendations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_paper_trades_id"), "paper_trades", ["id"], unique=False)
    op.create_index(op.f("ix_paper_trades_market_id"), "paper_trades", ["market_id"], unique=False)
    op.create_index(op.f("ix_paper_trades_recommendation_id"), "paper_trades", ["recommendation_id"], unique=False)
    op.create_index(op.f("ix_paper_trades_status"), "paper_trades", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_paper_trades_status"), table_name="paper_trades")
    op.drop_index(op.f("ix_paper_trades_recommendation_id"), table_name="paper_trades")
    op.drop_index(op.f("ix_paper_trades_market_id"), table_name="paper_trades")
    op.drop_index(op.f("ix_paper_trades_id"), table_name="paper_trades")
    op.drop_table("paper_trades")

    op.drop_index(op.f("ix_ev_recommendations_price_snapshot_id"), table_name="ev_recommendations")
    op.drop_index(op.f("ix_ev_recommendations_prediction_id"), table_name="ev_recommendations")
    op.drop_index(op.f("ix_ev_recommendations_id"), table_name="ev_recommendations")
    op.drop_table("ev_recommendations")

    op.drop_index(op.f("ix_predictions_parsed_market_id"), table_name="predictions")
    op.drop_index(op.f("ix_predictions_market_id"), table_name="predictions")
    op.drop_index(op.f("ix_predictions_id"), table_name="predictions")
    op.drop_index(op.f("ix_predictions_forecast_snapshot_id"), table_name="predictions")
    op.drop_table("predictions")

    op.drop_index(op.f("ix_weather_forecast_snapshots_parsed_market_id"), table_name="weather_forecast_snapshots")
    op.drop_index(op.f("ix_weather_forecast_snapshots_id"), table_name="weather_forecast_snapshots")
    op.drop_table("weather_forecast_snapshots")

    op.drop_index(op.f("ix_resolved_outcomes_market_id"), table_name="resolved_outcomes")
    op.drop_index(op.f("ix_resolved_outcomes_id"), table_name="resolved_outcomes")
    op.drop_table("resolved_outcomes")

    op.drop_index(op.f("ix_parsed_markets_market_id"), table_name="parsed_markets")
    op.drop_index(op.f("ix_parsed_markets_id"), table_name="parsed_markets")
    op.drop_table("parsed_markets")

    op.drop_index(op.f("ix_market_price_snapshots_timestamp"), table_name="market_price_snapshots")
    op.drop_index(op.f("ix_market_price_snapshots_market_id"), table_name="market_price_snapshots")
    op.drop_index(op.f("ix_market_price_snapshots_id"), table_name="market_price_snapshots")
    op.drop_table("market_price_snapshots")

    op.drop_index(op.f("ix_markets_source_market_id"), table_name="markets")
    op.drop_index(op.f("ix_markets_source"), table_name="markets")
    op.drop_index(op.f("ix_markets_id"), table_name="markets")
    op.drop_index(op.f("ix_markets_condition_id"), table_name="markets")
    op.drop_index(op.f("ix_markets_closed"), table_name="markets")
    op.drop_index(op.f("ix_markets_category"), table_name="markets")
    op.drop_index(op.f("ix_markets_active"), table_name="markets")
    op.drop_table("markets")

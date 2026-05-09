"""Add persisted paper runner runs.

Revision ID: 20260509_0003
Revises: 20260508_0002
Create Date: 2026-05-09 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260509_0003"
down_revision: str | None = "20260508_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_runner_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("discovered", sa.Integer(), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("updated", sa.Integer(), nullable=False),
        sa.Column("price_snapshots_created", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("parsed", sa.Integer(), nullable=False),
        sa.Column("forecasts_created", sa.Integer(), nullable=False),
        sa.Column("predictions_created", sa.Integer(), nullable=False),
        sa.Column("recommendations_created", sa.Integer(), nullable=False),
        sa.Column("paper_trades_created", sa.Integer(), nullable=False),
        sa.Column("skipped_json", sa.JSON(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_paper_runner_runs_id"), "paper_runner_runs", ["id"], unique=False)
    op.create_index(op.f("ix_paper_runner_runs_source"), "paper_runner_runs", ["source"], unique=False)
    op.create_index(op.f("ix_paper_runner_runs_started_at"), "paper_runner_runs", ["started_at"], unique=False)
    op.create_index(op.f("ix_paper_runner_runs_status"), "paper_runner_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_paper_runner_runs_status"), table_name="paper_runner_runs")
    op.drop_index(op.f("ix_paper_runner_runs_started_at"), table_name="paper_runner_runs")
    op.drop_index(op.f("ix_paper_runner_runs_source"), table_name="paper_runner_runs")
    op.drop_index(op.f("ix_paper_runner_runs_id"), table_name="paper_runner_runs")
    op.drop_table("paper_runner_runs")

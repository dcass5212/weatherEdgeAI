"""Add paper trade signal snapshots.

Revision ID: 20260510_0004
Revises: 20260509_0003
Create Date: 2026-05-10 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260510_0004"
down_revision: str | None = "20260509_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("paper_trades", sa.Column("signal_snapshot_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("paper_trades", "signal_snapshot_json")

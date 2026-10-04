"""profiles and runs

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("engine", sa.String(32), nullable=False),
        sa.Column("executable_path", sa.Text(), nullable=False),
        sa.Column("model_path", sa.Text(), nullable=True),
        sa.Column("alias", sa.String(255), nullable=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("ctx_size", sa.Integer(), nullable=True),
        sa.Column("n_gpu_layers", sa.Integer(), nullable=True),
        sa.Column("extra_args", sa.JSON(), nullable=False),
        sa.Column("env", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "profile_id",
            sa.String(32),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("command", sa.JSON(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("health_url", sa.Text(), nullable=False),
        sa.Column("log_path", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("stopped_at", sa.DateTime(), nullable=True),
        sa.Column("exit_reason", sa.String(32), nullable=True),
    )
    op.create_index("ix_runs_profile_id", "runs", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_profile_id", table_name="runs")
    op.drop_table("runs")
    op.drop_table("profiles")

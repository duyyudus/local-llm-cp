"""profile engine options

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-06
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("engine_options", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("engine_options")

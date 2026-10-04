"""profile working directory

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("working_dir", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("working_dir")

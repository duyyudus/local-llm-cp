"""profile position

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-06
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    # Profiles were listed by name until now; keep that as the starting order.
    bind = op.get_bind()
    ids = bind.execute(sa.text("SELECT id FROM profiles ORDER BY name")).scalars().all()
    for position, profile_id in enumerate(ids):
        bind.execute(
            sa.text("UPDATE profiles SET position = :position WHERE id = :id"),
            {"position": position, "id": profile_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("position")

"""Initial schema - event store and snapshots

Revision ID: 001
Revises:
Create Date: 2026-06-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Event store table
    op.create_table(
        "events",
        sa.Column("event_id", UUID, primary_key=True),
        sa.Column("stream_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("data", JSONB, nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("stream_id", "version", name="uq_events_stream_version"),
    )
    op.create_index("idx_events_stream_id", "events", ["stream_id"])
    op.create_index("idx_events_event_type", "events", ["event_type"])
    op.create_index("idx_events_aggregate_id", "events", ["aggregate_id"])
    op.create_index("idx_events_occurred_at", "events", ["occurred_at"])
    op.create_index("idx_events_data_gin", "events", ["data"], postgresql_using="gin")

    # Snapshots table
    op.create_table(
        "snapshots",
        sa.Column("aggregate_id", sa.String(255), primary_key=True),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("data", JSONB, nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_snapshots_aggregate_type", "snapshots", ["aggregate_type"])

    # Idempotency keys table
    op.create_table(
        "idempotency_keys",
        sa.Column("idempotency_key", sa.String(255), primary_key=True),
        sa.Column("response", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Outbox table for reliable event publishing
    op.create_table(
        "outbox",
        sa.Column("id", UUID, primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("data", JSONB, nullable=False, server_default="{}"),
        sa.Column("published", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_outbox_published", "outbox", ["published"],
                    postgresql_where=sa.text("published = false"))


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("idempotency_keys")
    op.drop_table("snapshots")
    op.drop_table("events")

"""Add api_keys lookup table for fast API key resolution.

This table provides O(1) lookup for key_id → (agent_id, key_hash),
complementing the event store for performance-critical authentication paths.

Revision ID: 003
Revises: 002
Create Date: 2026-06-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("key_id", sa.String(64), primary_key=True, comment="Unique key identifier"),
        sa.Column("agent_id", sa.String(255), nullable=False, comment="Associated agent ID"),
        sa.Column("key_hash", sa.String(255), nullable=False, comment="Bcrypt hash of the API key"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, comment="Key expiration timestamp"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False, comment="Whether key is revoked"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True, comment="When key was revoked"),
        comment="Fast lookup table for API key authentication",
    )

    # Index for agent_id lookups (list all keys for an agent)
    op.create_index("idx_api_keys_agent_id", "api_keys", ["agent_id"])

    # Index for active key lookups (used by scheduled expiration job)
    op.create_index("idx_api_keys_expires_at", "api_keys", ["expires_at"])

    # Composite index for authentication path (key_id + not revoked)
    op.create_index("idx_api_keys_active", "api_keys", ["key_id"], postgresql_where=sa.text("NOT revoked"))


def downgrade() -> None:
    op.drop_index("idx_api_keys_active", table_name="api_keys")
    op.drop_index("idx_api_keys_expires_at", table_name="api_keys")
    op.drop_index("idx_api_keys_agent_id", table_name="api_keys")
    op.drop_table("api_keys")

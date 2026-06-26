"""Add UNIQUE(stream_id, version) constraint for OCC.

This constraint ensures that no two events can be inserted with the same
version for the same stream, providing optimistic concurrency control (OCC)
at the database level. Combined with the IntegrityError catch in the
PostgresEventStore, this prevents data corruption from concurrent writes.

Revision ID: 004
Revises: 003
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicate events first (if any exist from before the constraint)
    op.execute("""
        DELETE FROM events e1
        USING events e2
        WHERE e1.ctid < e2.ctid
          AND e1.stream_id = e2.stream_id
          AND e1.version = e2.version
    """)

    # Add the UNIQUE constraint for OCC
    op.create_unique_constraint(
        "uq_stream_version",
        "events",
        ["stream_id", "version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_stream_version", "events", type_="unique")

"""Analytics materialized views for business metrics

Revision ID: 002
Revises: 001
Create Date: 2026-06-10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Daily revenue materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_revenue AS
        SELECT
            DATE(e.occurred_at) AS date,
            COUNT(DISTINCT e.aggregate_id) AS unique_agents,
            COUNT(*) AS total_sessions,
            SUM((e.data->>'amount')::numeric) AS revenue,
            AVG((e.data->>'amount')::numeric) AS avg_session_value
        FROM events e
        WHERE e.event_type = 'BillingSessionCompleted'
        GROUP BY DATE(e.occurred_at)
        WITH DATA;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_revenue_date
        ON mv_daily_revenue(date);
    """)

    # Agent activity summary materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_agent_activity AS
        SELECT
            e.aggregate_id AS agent_id,
            COUNT(*) AS total_events,
            COUNT(*) FILTER (WHERE e.event_type = 'PaymentFailed') AS failed_payments,
            COUNT(*) FILTER (WHERE e.event_type = 'BillingSessionStarted') AS sessions_started,
            COUNT(*) FILTER (WHERE e.event_type = 'BillingSessionCompleted') AS sessions_completed,
            COUNT(*) FILTER (WHERE e.event_type = 'AgentDelegated') AS delegations_created,
            COUNT(*) FILTER (WHERE e.event_type = 'AgentDelegationRevoked') AS delegations_revoked,
            MAX(e.occurred_at) AS last_activity,
            MIN(e.occurred_at) AS first_activity
        FROM events e
        WHERE e.occurred_at >= NOW() - INTERVAL '30 days'
        GROUP BY e.aggregate_id
        WITH DATA;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_agent_activity_agent
        ON mv_agent_activity(agent_id);
    """)

    # Resource consumption materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_resource_consumption AS
        SELECT
            DATE_TRUNC('hour', e.occurred_at) AS bucket,
            e.data->>'resource_type' AS resource_type,
            COUNT(*) AS consumption_count,
            SUM((e.data->>'amount')::numeric) AS total_amount,
            COUNT(DISTINCT e.aggregate_id) AS unique_agents
        FROM events e
        WHERE e.event_type = 'ResourceConsumed'
          AND e.occurred_at >= NOW() - INTERVAL '7 days'
        GROUP BY bucket, resource_type
        WITH DATA;

        CREATE INDEX IF NOT EXISTS idx_mv_resource_consumption_bucket
        ON mv_resource_consumption(bucket DESC);
    """)

    # Payment success rate materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_payment_success AS
        SELECT
            DATE_TRUNC('hour', e.occurred_at) AS bucket,
            COUNT(*) FILTER (WHERE e.event_type = 'PaymentVerified') AS successful_payments,
            COUNT(*) FILTER (WHERE e.event_type = 'PaymentFailed') AS failed_payments,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE e.event_type = 'PaymentVerified')
                / NULLIF(COUNT(*), 0),
                2
            ) AS success_rate_pct
        FROM events e
        WHERE e.event_type IN ('PaymentVerified', 'PaymentFailed')
          AND e.occurred_at >= NOW() - INTERVAL '7 days'
        GROUP BY bucket
        WITH DATA;

        CREATE INDEX IF NOT EXISTS idx_mv_payment_success_bucket
        ON mv_payment_success(bucket DESC);
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_revenue CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_agent_activity CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_resource_consumption CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_payment_success CASCADE")

"""Analytical SQL queries for business metrics and reporting.

This module provides a library of SQL queries for extracting
business intelligence from the event store. All queries are
designed to work with the PostgreSQL event store schema.

Usage:
    from app.analytics.queries import AnalyticsQueries

    # Get revenue by agent for the last 7 days
    query = AnalyticsQueries.revenue_by_agent(days=7)
    result = await session.execute(query)
"""

from datetime import datetime, timedelta, timezone


class AnalyticsQueries:
    """Library of analytical SQL queries for business metrics."""

    @staticmethod
    def revenue_by_agent(days: int = 7) -> str:
        """Total revenue and session count grouped by agent.

        Args:
            days: Number of days to look back

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            e.aggregate_id AS agent_id,
            COUNT(DISTINCT e.event_id) AS total_sessions,
            SUM((e.data->>'amount')::numeric) AS total_revenue,
            AVG((e.data->>'amount')::numeric) AS avg_session_value,
            MIN(e.occurred_at) AS first_activity,
            MAX(e.occurred_at) AS last_activity
        FROM events e
        WHERE e.event_type = 'BillingSessionCompleted'
          AND e.occurred_at >= NOW() - INTERVAL '{days} days'
        GROUP BY e.aggregate_id
        ORDER BY total_revenue DESC
        """

    @staticmethod
    def resource_consumption_trends(
        interval: str = "hour",
        days: int = 7,
    ) -> str:
        """Resource consumption trends over time.

        Args:
            interval: Time bucket interval ('hour', 'day', 'week')
            days: Number of days to look back

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            DATE_TRUNC('{interval}', e.occurred_at) AS bucket,
            e.data->>'resource_type' AS resource_type,
            COUNT(*) AS consumption_count,
            SUM((e.data->>'amount')::numeric) AS total_amount,
            COUNT(DISTINCT e.aggregate_id) AS unique_agents
        FROM events e
        WHERE e.event_type = 'ResourceConsumed'
          AND e.occurred_at >= NOW() - INTERVAL '{days} days'
        GROUP BY bucket, resource_type
        ORDER BY bucket DESC, total_amount DESC
        """

    @staticmethod
    def agent_activity_summary(days: int = 30) -> str:
        """Summary of agent activity and health.

        Args:
            days: Number of days to look back

        Returns:
            SQL query string
        """
        return f"""
        WITH agent_events AS (
            SELECT
                e.aggregate_id,
                COUNT(*) AS total_events,
                COUNT(*) FILTER (WHERE e.event_type = 'PaymentFailed') AS failed_payments,
                COUNT(*) FILTER (WHERE e.event_type = 'BillingSessionStarted') AS sessions_started,
                COUNT(*) FILTER (WHERE e.event_type = 'BillingSessionCompleted') AS sessions_completed,
                COUNT(*) FILTER (WHERE e.event_type = 'AgentDelegated') AS delegations_created,
                COUNT(*) FILTER (WHERE e.event_type = 'AgentDelegationRevoked') AS delegations_revoked,
                MAX(e.occurred_at) AS last_activity
            FROM events e
            WHERE e.occurred_at >= NOW() - INTERVAL '{days} days'
            GROUP BY e.aggregate_id
        )
        SELECT
            aggregate_id,
            total_events,
            failed_payments,
            sessions_started,
            sessions_completed,
            delegations_created,
            delegations_revoked,
            last_activity,
            CASE
                WHEN last_activity >= NOW() - INTERVAL '1 day' THEN 'active'
                WHEN last_activity >= NOW() - INTERVAL '7 days' THEN 'idle'
                ELSE 'inactive'
            END AS activity_status,
            CASE
                WHEN total_events = 0 THEN 0
                ELSE ROUND(100.0 * failed_payments / total_events, 2)
            END AS failure_rate_pct
        FROM agent_events
        ORDER BY total_events DESC
        """

    @staticmethod
    def delegation_analytics(days: int = 30) -> str:
        """Delegation usage analytics.

        Args:
            days: Number of days to look back

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            DATE_TRUNC('day', e.occurred_at) AS date,
            e.event_type,
            COUNT(*) AS event_count,
            COUNT(DISTINCT e.aggregate_id) AS unique_agents
        FROM events e
        WHERE e.event_type IN ('AgentDelegated', 'AgentDelegationRevoked')
          AND e.occurred_at >= NOW() - INTERVAL '{days} days'
        GROUP BY date, e.event_type
        ORDER BY date DESC
        """

    @staticmethod
    def payment_success_rate(days: int = 7) -> str:
        """Payment success/failure rate over time.

        Args:
            days: Number of days to look back

        Returns:
            SQL query string
        """
        return f"""
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
          AND e.occurred_at >= NOW() - INTERVAL '{days} days'
        GROUP BY bucket
        ORDER BY bucket DESC
        """

    @staticmethod
    def top_agents_by_consumption(
        resource_type: str = None,
        days: int = 7,
        limit: int = 20,
    ) -> str:
        """Top agents by resource consumption.

        Args:
            resource_type: Optional filter by resource type
            days: Number of days to look back
            limit: Maximum number of agents to return

        Returns:
            SQL query string
        """
        resource_filter = (
            f"AND e.data->>'resource_type' = '{resource_type}'"
            if resource_type
            else ""
        )
        return f"""
        SELECT
            e.aggregate_id AS agent_id,
            e.data->>'resource_type' AS resource_type,
            COUNT(*) AS consumption_count,
            SUM((e.data->>'amount')::numeric) AS total_amount,
            AVG((e.data->>'amount')::numeric) AS avg_amount
        FROM events e
        WHERE e.event_type = 'ResourceConsumed'
          AND e.occurred_at >= NOW() - INTERVAL '{days} days'
          {resource_filter}
        GROUP BY e.aggregate_id, resource_type
        ORDER BY total_amount DESC
        LIMIT {limit}
        """

    @staticmethod
    def daily_active_agents(days: int = 30) -> str:
        """Daily active agent count.

        Args:
            days: Number of days to look back

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            DATE(e.occurred_at) AS date,
            COUNT(DISTINCT e.aggregate_id) AS active_agents,
            COUNT(*) AS total_events
        FROM events e
        WHERE e.occurred_at >= NOW() - INTERVAL '{days} days'
        GROUP BY date
        ORDER BY date DESC
        """

    @staticmethod
    def billing_session_duration(days: int = 7) -> str:
        """Average billing session duration.

        Args:
            days: Number of days to look back

        Returns:
            SQL query string
        """
        return f"""
        WITH session_times AS (
            SELECT
                e.aggregate_id,
                MIN(e.occurred_at) AS started_at,
                MAX(e.occurred_at) AS completed_at,
                EXTRACT(EPOCH FROM MAX(e.occurred_at) - MIN(e.occurred_at)) AS duration_seconds
            FROM events e
            WHERE e.event_type IN ('BillingSessionStarted', 'BillingSessionCompleted')
              AND e.occurred_at >= NOW() - INTERVAL '{days} days'
            GROUP BY e.aggregate_id
            HAVING COUNT(*) >= 2
        )
        SELECT
            AVG(duration_seconds)::INTEGER AS avg_duration_seconds,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_seconds) AS median_duration_seconds,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_seconds) AS p95_duration_seconds,
            MAX(duration_seconds)::INTEGER AS max_duration_seconds,
            COUNT(*) AS total_sessions
        FROM session_times
        """

    @staticmethod
    def invoice_summary(days: int = 30) -> str:
        """Invoice generation and payment summary.

        Args:
            days: Number of days to look back

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            DATE_TRUNC('day', e.occurred_at) AS date,
            COUNT(*) FILTER (WHERE e.event_type = 'InvoiceGenerated') AS invoices_generated,
            COUNT(*) FILTER (WHERE e.event_type = 'InvoicePaid') AS invoices_paid,
            SUM((e.data->>'amount')::numeric) FILTER (WHERE e.event_type = 'InvoiceGenerated') AS total_invoiced,
            SUM((e.data->>'amount')::numeric) FILTER (WHERE e.event_type = 'InvoicePaid') AS total_collected
        FROM events e
        WHERE e.event_type IN ('InvoiceGenerated', 'InvoicePaid')
          AND e.occurred_at >= NOW() - INTERVAL '{days} days'
        GROUP BY date
        ORDER BY date DESC
        """

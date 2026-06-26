"""TimescaleDB time-series queries for performance monitoring.

These queries require TimescaleDB hypertables to be configured.
They provide high-resolution time-series data for dashboards
and performance monitoring.

Usage:
    from app.analytics.timescale_queries import TimescaleQueries

    query = TimescaleQueries.api_performance(hours=24)
    result = await session.execute(query)
"""


class TimescaleQueries:
    """Time-series queries for performance monitoring with TimescaleDB."""

    @staticmethod
    def api_performance(hours: int = 24) -> str:
        """API performance metrics (latency, throughput) over time.

        Requires a 'metrics' hypertable with columns:
            - timestamp (timestamptz)
            - endpoint (text)
            - response_time_ms (numeric)
            - status_code (int)
            - agent_id (text)

        Args:
            hours: Lookback window in hours

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            time_bucket('5 minutes', timestamp) AS bucket,
            endpoint,
            COUNT(*) AS request_count,
            AVG(response_time_ms)::INTEGER AS avg_latency_ms,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms) AS p50_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) AS p95_latency_ms,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) AS p99_latency_ms,
            MAX(response_time_ms)::INTEGER AS max_latency_ms,
            COUNT(*) FILTER (WHERE status_code >= 500) AS server_errors,
            COUNT(*) FILTER (WHERE status_code >= 400 AND status_code < 500) AS client_errors
        FROM metrics
        WHERE timestamp >= NOW() - INTERVAL '{hours} hours'
        GROUP BY bucket, endpoint
        ORDER BY bucket DESC
        """

    @staticmethod
    def blockchain_interaction_metrics(hours: int = 24) -> str:
        """Blockchain interaction performance metrics.

        Requires a 'blockchain_metrics' hypertable with columns:
            - timestamp (timestamptz)
            - operation (text) - 'verify_payment', 'check_delegation', etc.
            - gas_used (numeric)
            - block_number (bigint)
            - duration_ms (numeric)
            - success (boolean)

        Args:
            hours: Lookback window in hours

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            time_bucket('1 hour', timestamp) AS bucket,
            operation,
            COUNT(*) AS total_calls,
            AVG(gas_used)::INTEGER AS avg_gas_used,
            SUM(gas_used) AS total_gas_used,
            AVG(duration_ms)::INTEGER AS avg_duration_ms,
            COUNT(*) FILTER (WHERE success = false) AS failed_calls,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE success = true) / NULLIF(COUNT(*), 0),
                2
            ) AS success_rate_pct
        FROM blockchain_metrics
        WHERE timestamp >= NOW() - INTERVAL '{hours} hours'
        GROUP BY bucket, operation
        ORDER BY bucket DESC
        """

    @staticmethod
    def redis_performance(hours: int = 24) -> str:
        """Redis cache performance metrics.

        Requires a 'redis_metrics' hypertable with columns:
            - timestamp (timestamptz)
            - operation (text) - 'get', 'set', 'lua_script', etc.
            - duration_us (numeric)
            - cache_hit (boolean)

        Args:
            hours: Lookback window in hours

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            time_bucket('5 minutes', timestamp) AS bucket,
            operation,
            COUNT(*) AS total_ops,
            AVG(duration_us)::INTEGER AS avg_duration_us,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_us) AS p95_duration_us,
            COUNT(*) FILTER (WHERE cache_hit = true) AS cache_hits,
            COUNT(*) FILTER (WHERE cache_hit = false) AS cache_misses,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE cache_hit = true) / NULLIF(COUNT(*), 0),
                2
            ) AS hit_rate_pct
        FROM redis_metrics
        WHERE timestamp >= NOW() - INTERVAL '{hours} hours'
        GROUP BY bucket, operation
        ORDER BY bucket DESC
        """

    @staticmethod
    def kafka_stream_metrics(hours: int = 24) -> str:
        """Kafka event stream metrics.

        Requires a 'kafka_metrics' hypertable with columns:
            - timestamp (timestamptz)
            - topic (text)
            - partition (int)
            - lag (bigint)
            - messages_per_second (numeric)

        Args:
            hours: Lookback window in hours

        Returns:
            SQL query string
        """
        return f"""
        SELECT
            time_bucket('5 minutes', timestamp) AS bucket,
            topic,
            AVG(lag)::INTEGER AS avg_lag,
            MAX(lag)::INTEGER AS max_lag,
            AVG(messages_per_second)::INTEGER AS avg_throughput,
            MAX(messages_per_second)::INTEGER AS peak_throughput
        FROM kafka_metrics
        WHERE timestamp >= NOW() - INTERVAL '{hours} hours'
        GROUP BY bucket, topic
        ORDER BY bucket DESC
        """

    @staticmethod
    def resource_usage_timeseries(
        resource_type: str | None = None,
        hours: int = 24,
        bucket: str = "5 minutes",
    ) -> str:
        """Resource usage time-series for specific resource types.

        Args:
            resource_type: Optional filter (e.g., 'llm', 'stt')
            hours: Lookback window
            bucket: Time bucket interval

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
            time_bucket('{bucket}', e.occurred_at) AS bucket,
            e.data->>'resource_type' AS resource_type,
            COUNT(*) AS usage_count,
            SUM((e.data->>'amount')::numeric) AS total_amount,
            COUNT(DISTINCT e.aggregate_id) AS unique_agents
        FROM events e
        WHERE e.event_type = 'ResourceConsumed'
          AND e.occurred_at >= NOW() - INTERVAL '{hours} hours'
          {resource_filter}
        GROUP BY bucket, resource_type
        ORDER BY bucket DESC
        """

    @staticmethod
    def create_hypertables() -> str:
        """SQL to create TimescaleDB hypertables for metrics.

        Run this once to set up the hypertables required by
        the time-series queries above.
        """
        return """
        -- API performance metrics
        CREATE TABLE IF NOT EXISTS metrics (
            timestamp TIMESTAMPTZ NOT NULL,
            endpoint TEXT NOT NULL,
            response_time_ms NUMERIC NOT NULL,
            status_code INTEGER NOT NULL,
            agent_id TEXT
        );
        SELECT create_hypertable('metrics', 'timestamp',
            if_not_exists => TRUE);

        -- Blockchain interaction metrics
        CREATE TABLE IF NOT EXISTS blockchain_metrics (
            timestamp TIMESTAMPTZ NOT NULL,
            operation TEXT NOT NULL,
            gas_used NUMERIC,
            block_number BIGINT,
            duration_ms NUMERIC,
            success BOOLEAN DEFAULT TRUE
        );
        SELECT create_hypertable('blockchain_metrics', 'timestamp',
            if_not_exists => TRUE);

        -- Redis cache metrics
        CREATE TABLE IF NOT EXISTS redis_metrics (
            timestamp TIMESTAMPTZ NOT NULL,
            operation TEXT NOT NULL,
            duration_us NUMERIC,
            cache_hit BOOLEAN
        );
        SELECT create_hypertable('redis_metrics', 'timestamp',
            if_not_exists => TRUE);

        -- Kafka stream metrics
        CREATE TABLE IF NOT EXISTS kafka_metrics (
            timestamp TIMESTAMPTZ NOT NULL,
            topic TEXT NOT NULL,
            partition INTEGER,
            lag BIGINT,
            messages_per_second NUMERIC
        );
        SELECT create_hypertable('kafka_metrics', 'timestamp',
            if_not_exists => TRUE);
        """

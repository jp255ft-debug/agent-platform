"""Script to refresh materialized views for analytics.

This script should be scheduled to run periodically (e.g., every hour)
to keep the materialized views up to date.

Usage:
    python -m scripts.reconciliation.refresh_views
    python -m scripts.reconciliation.refresh_views --concurrently
"""

import argparse
import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from scripts.reconciliation.config import config

logger = logging.getLogger(__name__)

# Materialized views to refresh
MATERIALIZED_VIEWS = [
    "mv_daily_revenue",
    "mv_agent_activity",
    "mv_resource_consumption",
    "mv_payment_success",
]


async def refresh_views(concurrently: bool = False):
    """Refresh all materialized views."""
    engine = create_async_engine(config.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    concurrently_clause = "CONCURRENTLY" if concurrently else ""

    async with session_factory() as session:
        for view_name in MATERIALIZED_VIEWS:
            try:
                logger.info(f"Refreshing materialized view: {view_name}")
                await session.execute(
                    text(
                        f"REFRESH MATERIALIZED VIEW {concurrently_clause} {view_name}"
                    )
                )
                logger.info(f"Successfully refreshed: {view_name}")
            except Exception as e:
                logger.error(f"Failed to refresh {view_name}: {e}")

        await session.commit()

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Refresh analytics materialized views"
    )
    parser.add_argument(
        "--concurrently",
        action="store_true",
        help="Refresh concurrently (allows reads during refresh)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    asyncio.run(refresh_views(concurrently=args.concurrently))


if __name__ == "__main__":
    main()

"""Inspect or remove expired safeguard telemetry."""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import asyncpg


class SafeguardCleanupError(RuntimeError):
    """Raised when safeguard retention cannot be inspected safely."""


@dataclass(frozen=True, slots=True)
class CleanupCounts:
    counters: int
    alerts: int
    events: int


async def cleanup_safeguards(
    connection: asyncpg.Connection,
    *,
    before: datetime,
    apply: bool = False,
) -> CleanupCounts:
    if before.tzinfo is None:
        raise SafeguardCleanupError("The retention cutoff must include a timezone.")

    async with connection.transaction():
        counters = await connection.fetchval(
            """
            select count(*) from public.quota_counters
            where window_start + make_interval(secs => window_seconds) < $1
            """,
            before,
        )
        alerts = await connection.fetchval(
            "select count(*) from public.quota_alerts where created_at < $1",
            before,
        )
        events = await connection.fetchval(
            "select count(*) from public.usage_events where created_at < $1",
            before,
        )
        counts = CleanupCounts(int(counters or 0), int(alerts or 0), int(events or 0))
        if apply:
            await connection.execute(
                """
                delete from public.quota_counters
                where window_start + make_interval(secs => window_seconds) < $1
                """,
                before,
            )
            await connection.execute(
                "delete from public.quota_alerts where created_at < $1",
                before,
            )
            await connection.execute(
                "delete from public.usage_events where created_at < $1",
                before,
            )
        return counts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or remove safeguard records older than the retention window."
    )
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit deletion. Without this flag, the command is read-only.",
    )
    return parser


async def _run(*, retention_days: int, apply: bool) -> None:
    if retention_days < 1:
        raise SafeguardCleanupError("Retention days must be at least 1.")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SafeguardCleanupError("DATABASE_URL must identify the database to inspect.")
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    connection = await asyncpg.connect(database_url)
    try:
        counts = await cleanup_safeguards(connection, before=cutoff, apply=apply)
    finally:
        await connection.close()

    print(f"Safeguard cleanup: {'APPLIED' if apply else 'DRY RUN'}")
    print(f"Retention cutoff: {cutoff.isoformat()}")
    print(f"Expired quota counters: {counts.counters}")
    print(f"Expired alert markers: {counts.alerts}")
    print(f"Expired usage events: {counts.events}")
    if not apply:
        print("No changes applied. Re-run with --apply after reviewing these counts.")


def main() -> int:
    arguments = _parser().parse_args()
    try:
        asyncio.run(_run(retention_days=arguments.retention_days, apply=arguments.apply))
    except (SafeguardCleanupError, OSError, asyncpg.PostgresError) as error:
        print(f"Safeguard cleanup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

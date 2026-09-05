"""Claim pre-authentication documents and queries for an explicit user."""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from uuid import UUID

import asyncpg


class OwnershipBackfillError(RuntimeError):
    """Raised when ownership cannot be assigned safely."""


@dataclass(frozen=True, slots=True)
class OwnershipCounts:
    documents: int
    queries: int
    mismatched_scoped_queries: int
    missing_storage_objects: int


@dataclass(frozen=True, slots=True)
class OwnershipClaimReport:
    owner_id: UUID
    applied: bool
    before: OwnershipCounts
    after: OwnershipCounts | None = None


async def inspect_legacy_ownership(
    connection: asyncpg.Connection,
    owner_id: UUID,
) -> OwnershipCounts:
    owner_exists = await connection.fetchval(
        "select exists(select 1 from auth.users where id = $1)",
        owner_id,
    )
    if owner_exists is not True:
        raise OwnershipBackfillError(
            f"No Supabase Auth user exists with ID {owner_id}. No changes were made."
        )

    row = await connection.fetchrow(
        """
        select
          (select count(*) from public.documents where owner_id is null) as documents,
          (select count(*) from public.queries where user_id is null) as queries,
          (
            select count(*)
            from public.queries q
            join public.documents d on d.id = q.document_id
            where q.document_id is not null
              and coalesce(q.user_id, $1) <> coalesce(d.owner_id, $1)
          ) as mismatched_scoped_queries,
          (
            select count(*)
            from public.documents d
            left join storage.objects so
              on so.bucket_id = 'documents' and so.name = d.storage_path
            where d.owner_id is null and so.id is null
          ) as missing_storage_objects
        """,
        owner_id,
    )
    if row is None:
        raise OwnershipBackfillError("The database did not return ownership counts.")
    return OwnershipCounts(
        documents=int(row["documents"]),
        queries=int(row["queries"]),
        mismatched_scoped_queries=int(row["mismatched_scoped_queries"]),
        missing_storage_objects=int(row["missing_storage_objects"]),
    )


async def claim_legacy_ownership(
    connection: asyncpg.Connection,
    owner_id: UUID,
    *,
    apply: bool = False,
) -> OwnershipClaimReport:
    before = await inspect_legacy_ownership(connection, owner_id)
    if before.mismatched_scoped_queries:
        raise OwnershipBackfillError(
            "Existing document-scoped queries have conflicting owners. "
            "Resolve them manually before running the ownership backfill."
        )
    if not apply:
        return OwnershipClaimReport(owner_id=owner_id, applied=False, before=before)

    async with connection.transaction():
        await connection.execute(
            "lock table public.documents, public.queries in share row exclusive mode"
        )
        locked_counts = await inspect_legacy_ownership(connection, owner_id)
        if locked_counts.mismatched_scoped_queries:
            raise OwnershipBackfillError(
                "Ownership changed after the dry run. No changes were committed."
            )
        await connection.execute(
            """
            insert into public.profiles (user_id)
            values ($1)
            on conflict (user_id) do nothing
            """,
            owner_id,
        )
        await connection.execute(
            "update public.documents set owner_id = $1 where owner_id is null",
            owner_id,
        )
        await connection.execute(
            "update public.queries set user_id = $1 where user_id is null",
            owner_id,
        )
        after = await inspect_legacy_ownership(connection, owner_id)
        if after.documents or after.queries or after.mismatched_scoped_queries:
            raise OwnershipBackfillError(
                "Ownership verification failed. The transaction was rolled back."
            )

    return OwnershipClaimReport(
        owner_id=owner_id,
        applied=True,
        before=locked_counts,
        after=after,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or claim pre-authentication records for one Supabase Auth user."
    )
    parser.add_argument("--owner-id", required=True, type=UUID)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the assignment. Without this flag, the command is read-only.",
    )
    return parser


def _print_report(report: OwnershipClaimReport) -> None:
    mode = "APPLIED" if report.applied else "DRY RUN"
    print(f"Legacy ownership backfill: {mode}")
    print(f"Owner: {report.owner_id}")
    print(f"Ownerless documents: {report.before.documents}")
    print(f"Ownerless queries: {report.before.queries}")
    print(f"Mismatched scoped queries: {report.before.mismatched_scoped_queries}")
    print(f"Legacy documents missing storage metadata: {report.before.missing_storage_objects}")
    if report.applied and report.after is not None:
        print(f"Remaining ownerless documents: {report.after.documents}")
        print(f"Remaining ownerless queries: {report.after.queries}")
        print("Ownership assignment committed.")
    else:
        print("No changes applied. Use the apply command only after reviewing these counts.")


async def _run(owner_id: UUID, *, apply: bool) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise OwnershipBackfillError("DATABASE_URL must identify the database to inspect.")
    connection = await asyncpg.connect(database_url)
    try:
        report = await claim_legacy_ownership(connection, owner_id, apply=apply)
    finally:
        await connection.close()
    _print_report(report)


def main() -> int:
    arguments = _parser().parse_args()
    try:
        asyncio.run(_run(arguments.owner_id, apply=arguments.apply))
    except (OwnershipBackfillError, OSError, asyncpg.PostgresError) as error:
        print(f"Ownership backfill failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

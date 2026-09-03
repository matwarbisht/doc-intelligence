"""Postgres connection-pool configuration."""

import json

import asyncpg
from pgvector.asyncpg import register_vector


def _decode_json(value: str) -> object:
    return json.loads(value)


async def _configure_connection(connection: asyncpg.Connection) -> None:
    await connection.set_type_codec(
        "json",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=_decode_json,
        format="text",
    )
    await connection.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=_decode_json,
        format="text",
    )
    await register_vector(connection)


async def create_database_pool(database_url: str) -> asyncpg.Pool:
    """Create a pool with JSON and pgvector codecs registered."""

    return await asyncpg.create_pool(
        database_url, min_size=1, max_size=10, init=_configure_connection
    )

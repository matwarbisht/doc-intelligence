"""asyncpg profile persistence adapter."""

from typing import cast

import asyncpg

from app.domain import AuthenticatedUser, Profile


class PostgresProfileRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ensure(self, user: AuthenticatedUser) -> Profile:
        row = await self._pool.fetchrow(
            """
            with inserted as (
              insert into public.profiles (user_id)
              values ($1)
              on conflict (user_id) do nothing
              returning *
            )
            select * from inserted
            union all
            select * from public.profiles where user_id = $1
            limit 1
            """,
            user.id,
        )
        if row is None:
            raise RuntimeError("database did not return the authenticated profile")
        return Profile.model_validate(cast(object, dict(row)))

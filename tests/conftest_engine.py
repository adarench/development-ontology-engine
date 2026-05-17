"""Shared fixtures for engine integration tests.

Tests that need a real Postgres pull in `engine_session` from here.
The fixture wraps each test in a transaction that rolls back, so the DB stays
clean between tests. If Postgres is unreachable, the tests are skipped — no
extra setup required to run the unit suite.
"""
from __future__ import annotations

import asyncio
import os
from functools import lru_cache

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@lru_cache(maxsize=1)
def _postgres_reachable() -> bool:
    """Probe Postgres exactly once per pytest session. Cached so we don't pay
    a connect+dispose cost for every `@requires_postgres` test."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return False

    async def _probe() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_probe())
    except Exception:
        return False


def requires_postgres_factory():
    return pytest.mark.skipif(
        not _postgres_reachable(),
        reason="Postgres not reachable; skipping integration tests.",
    )


# Re-evaluated on import — fine because pytest collects modules once per run.
requires_postgres = requires_postgres_factory()


@pytest_asyncio.fixture
async def engine_session() -> AsyncSession:
    """Yields a session wrapped in a top-level transaction that rolls back at
    end-of-test. If the database isn't reachable, the test is skipped."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as e:  # noqa: BLE001 — broad on purpose; we just skip
            pytest.skip(f"Postgres unreachable at DATABASE_URL: {e}")

        async with engine.connect() as conn:
            trans = await conn.begin()
            factory = async_sessionmaker(
                bind=conn, expire_on_commit=False, class_=AsyncSession
            )
            async with factory() as session:
                try:
                    yield session
                finally:
                    await trans.rollback()
    finally:
        await engine.dispose()

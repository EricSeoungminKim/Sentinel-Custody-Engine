from typing import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from src.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    return create_async_engine(get_settings().database_url, echo=False)


def _make_session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache
def get_engine():
    return _make_engine()


@lru_cache
def get_session_factory():
    return _make_session_factory(get_engine())


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session

from collections import defaultdict
from contextlib import asynccontextmanager
import asyncio
from typing import AsyncIterator

_nonce_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@asynccontextmanager
async def nonce_lock(address: str) -> AsyncIterator[None]:
    lock = _nonce_locks[address.lower()]
    async with lock:
        yield

import asyncio
import asyncpg
import os


class Database:
    def __init__(self):
        self._pool = None
        self._connect_lock = asyncio.Lock()

    def _pool_ready(self):
        return self._pool is not None and not self._pool._closed

    async def connect(self):
        if self._pool_ready():
            return

        async with self._connect_lock:
            if self._pool_ready():
                return

            host = os.getenv("POSTGRES_HOST", "db")
            port = int(os.getenv("POSTGRES_PORT", "5432"))
            attempts = int(os.getenv("POSTGRES_CONNECT_RETRIES", "20"))
            delay_seconds = float(os.getenv("POSTGRES_CONNECT_DELAY", "1.5"))
            last_error = None

            for attempt in range(1, attempts + 1):
                try:
                    self._pool = await asyncpg.create_pool(
                        user=os.getenv("POSTGRES_USER"),
                        password=os.getenv("POSTGRES_PASSWORD"),
                        database=os.getenv("POSTGRES_DB"),
                        host=host,
                        port=port,
                    )
                    return
                except Exception as exc:
                    last_error = exc
                    if attempt == attempts:
                        break
                    await asyncio.sleep(delay_seconds)

            raise last_error

    async def execute(self, query, *params):
        await self.connect()
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                return await connection.fetch(query, *params)

    async def close(self):
        async with self._connect_lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None

db = Database()

import asyncio
from dataclasses import dataclass
from pathlib import Path

import aiosqlite
from aiosqlite import Connection
from loguru import logger

INIT_DB_QUERY = """
    CREATE TABLE IF NOT EXISTS rate (
        currency TEXT NOT NULL, 
        name TEXT NOT NULL, 
        js JSON NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('libor_rate', 'swap_rate')),
        PRIMARY KEY (currency, name, type)
    );

    CREATE TABLE IF NOT EXISTS vol_conventions (
        currency TEXT PRIMARY KEY,
        libor_rate TEXT NOT NULL,
        swap_rate TEXT NOT NULL,

        FOREIGN KEY (currency, libor_rate, 'libor_rate') REFERENCES libor_rate (currency, name, type),
        FOREIGN KEY (currency, swap_rate, 'swap_rate') REFERENCES swap_rate (currency, name, type)
    );

    CREATE TABLE IF NOT EXISTS generic_conventions (
        currency TEXT PRIMARY KEY,
        boundary_tenor TEXT NOT NULL
    );
"""


@dataclass
class Context:
    path: Path


async def init_db(db: Connection):
    logger.info("initializing database ..")
    await db.executescript(INIT_DB_QUERY)
    await db.commit()


if __name__ == "__main__":
    ctx = Context(Path.home() / ".local" / "share" / "arbitui" / "arbitui.db")

    async def run():
        ctx.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with aiosqlite.connect(ctx.path) as db:
                await init_db(db)
        except Exception as e:
            logger.error(f"failed to initialize db {e}")
            raise

    asyncio.run(run())

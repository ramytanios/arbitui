import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List

import aiosqlite
from loguru import logger

import dtos

INIT_DB_QUERY = """
    CREATE TABLE IF NOT EXISTS rate (
        currency TEXT NOT NULL, 
        name TEXT NOT NULL, 
        js JSON NOT NULL,
        PRIMARY KEY (currency, name)
    );

    CREATE TABLE IF NOT EXISTS vol_conventions (
        currency TEXT PRIMARY KEY,
        libor_rate TEXT NOT NULL,
        swap_rate TEXT NOT NULL,
        boundary_tenor TEXT NOT NULL,

        FOREIGN KEY (currency, libor_rate) REFERENCES libor_rate (currency, name),
        FOREIGN KEY (currency, swap_rate) REFERENCES swap_rate (currency, name)
    );

    INSERT INTO rate VALUES 
        ('EUR', 'ESTR', '{"currency": "EUR", "tenor": "1D", "spot_lag": 0, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "ESTR"}, "type": "Libor"}'),
        ('EUR', 'ESTR12M', '{"currency": "EUR", "tenor": "12M", "spot_lag": 2, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "ESTR"}, "type": "Libor"}'),
        ('EUR', 'EURIBOR3M', '{"currency": "EUR", "tenor": "3M", "spot_lag": 2, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "EURIBOR3M"}, "type": "Libor"}'),
        ('EUR', 'ESTR10Y', '{"currency": "EUR", "tenor": "1Y", "spot_lag": 2, "floating_rate": "ESTR12M", "fixed_frequency": "12M", "fixed_day_counter": "Act360", "payment_delay": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "ESTR"}, "type": "SwapRate"}'),
        ('EUR', 'EURIBOR10Y', '{"currency": "EUR", "tenor": "1Y", "spot_lag": 2, "floating_rate": "EURIBOR3M", "fixed_frequency": "3M", "fixed_day_counter": "Act360", "payment_delay": 0, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "ESTR"}, "type": "SwapRate"}'),
        ('USD', 'SOFR', '{"currency": "USD", "tenor": "1D", "spot_lag": 0, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "USD", "name": "SOFR"}, "type": "Libor"}'),
        ('USD', 'SOFR12M', '{"currency": "USD", "tenor": "12M", "spot_lag": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "day_counter": "Act360", "reset_curve": {"currency": "USD", "name": "SOFR"}, "type": "Libor"}'),
        ('USD', 'SOFR10Y', '{"currency": "USD", "tenor": "1Y", "spot_lag": 2, "floating_rate": "SOFR12M", "fixed_frequency": "12M", "fixed_day_counter": "Act360", "payment_delay": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "SOFR"}, "type": "SwapRate"}');


    INSERT INTO vol_conventions VALUES 
        ('EUR', 'ESTR', 'ESTR10Y', '1Y'),
        ('USD', 'SOFR', 'SOFR10Y', '1Y');

"""


@dataclass
class Context:
    path: Path


async def init_db(ctx: Context):
    logger.info("initializing database ..")
    try:
        async with aiosqlite.connect(ctx.path) as db:
            await db.executescript(INIT_DB_QUERY)
            await db.commit()
    except Exception as e:
        logger.error(f"failed to initialize db {e}")
        raise


async def get_rates_count(ctx: Context):
    async with aiosqlite.connect(ctx.path) as db:
        async with db.execute("SELECT COUNT(*) FROM rate") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_conventions_count(ctx: Context):
    async with aiosqlite.connect(ctx.path) as db:
        async with db.execute("SELECT COUNT(*) FROM vol_conventions") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_libor_rates(ccy: str, ctx: Context) -> List[dtos.Libor]:
    query = (
        "SELECT * FROM rate WHERE currency = ? AND json_extract(js, '$.type') = 'Libor'"
    )
    async with aiosqlite.connect(ctx.path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, (ccy,)) as cursor:
            rows = await cursor.fetchall()
            results = [dtos.Libor.model_validate_json(row["js"]) for row in rows]
            return results


async def get_swap_rates(ccy: str, ctx: Context) -> List[dtos.SwapRate]:
    query = "SELECT * FROM rate WHERE currency = ? AND json_extract(js, '$.type') = 'SwapRate'"
    async with aiosqlite.connect(ctx.path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, (ccy,)) as cursor:
            rows = await cursor.fetchall()
            results = [dtos.SwapRate.model_validate_json(row["js"]) for row in rows]
            return results


if __name__ == "__main__":
    ctx = Context(Path.home() / ".local" / "share" / "arbitui" / "arbitui-tst.db")
    ctx.path.parent.mkdir(parents=True, exist_ok=True)

    async def run():
        # await init_db(ctx)
        libor_rates = await get_libor_rates("USD", ctx)
        swap_rates = await get_swap_rates("USD", ctx)
        print(libor_rates)
        print(swap_rates)

    asyncio.run(run())

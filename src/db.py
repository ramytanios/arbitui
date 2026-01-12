import asyncio
import uuid
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

        FOREIGN KEY (currency, libor_rate) REFERENCES rate (currency, name),
        FOREIGN KEY (currency, swap_rate) REFERENCES rate (currency, name)
    );

    INSERT INTO rate VALUES 
        ('EUR', 'ESTR', '{"currency": "EUR", "tenor": "1D", "spot_lag": 0, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "ESTR"}, "type": "Libor"}'),
        ('EUR', 'ESTR12M', '{"currency": "EUR", "tenor": "12M", "spot_lag": 2, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "ESTR"}, "type": "Libor"}'),
        ('EUR', 'EURIBOR3M', '{"currency": "EUR", "tenor": "3M", "spot_lag": 2, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "EURIBOR3M"}, "type": "Libor"}'),
        ('EUR', 'ESTR10Y', '{"currency": "EUR", "tenor": "1Y", "spot_lag": 2, "floating_rate": "ESTR12M", "fixed_period": "12M", "fixed_day_counter": "Act360", "payment_delay": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "ESTR"}, "type": "SwapRate"}'),
        ('EUR', 'EURIBOR10Y', '{"currency": "EUR", "tenor": "1Y", "spot_lag": 2, "floating_rate": "EURIBOR3M", "fixed_period": "3M", "fixed_day_counter": "Act360", "payment_delay": 0, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "ESTR"}, "type": "SwapRate"}'),
        ('USD', 'SOFR', '{"currency": "USD", "tenor": "1D", "spot_lag": 0, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "USD", "name": "SOFR"}, "type": "Libor"}'),
        ('USD', 'SOFR12M', '{"currency": "USD", "tenor": "12M", "spot_lag": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "day_counter": "Act360", "reset_curve": {"currency": "USD", "name": "SOFR"}, "type": "Libor"}'),
        ('USD', 'SOFR10Y', '{"currency": "USD", "tenor": "1Y", "spot_lag": 2, "floating_rate": "SOFR12M", "fixed_period": "12M", "fixed_day_counter": "Act360", "payment_delay": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "SOFR"}, "type": "SwapRate"}');


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
    logger.info(f"querying database for {ccy} libor rates")
    async with aiosqlite.connect(ctx.path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, (ccy,)) as cursor:
            rows = await cursor.fetchall()
            results = [dtos.Libor.model_validate_json(row["js"]) for row in rows]
            return results


async def get_swap_rates(ccy: str, ctx: Context) -> List[dtos.SwapRate]:
    query = "SELECT * FROM rate WHERE currency = ? AND json_extract(js, '$.type') = 'SwapRate'"
    logger.info(f"querying database for {ccy} swap rates")
    async with aiosqlite.connect(ctx.path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, (ccy,)) as cursor:
            rows = await cursor.fetchall()
            results = [dtos.SwapRate.model_validate_json(row["js"]) for row in rows]
            return results


async def get_conventions(ccy: str, ctx: Context) -> dtos.VolatilityMarketConventions:
    query = """
        SELECT vc.boundary_tenor, r1.js AS libor_js, r2.js AS swap_js 
        FROM vol_conventions AS vc
        JOIN rate AS r1 ON vc.currency = r1.currency AND vc.libor_rate = r1.name
        JOIN rate AS r2 ON vc.currency = r2.currency AND vc.swap_rate = r2.name
        WHERE vc.currency = ?
    """
    logger.info(f"querying database for {ccy} conventions..")
    async with aiosqlite.connect(ctx.path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, (ccy,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise Exception(f"can't find {ccy} conventions")
            else:
                libor = dtos.Libor.model_validate_json(row["libor_js"]).to_conventions()
                swp = dtos.SwapRate.model_validate_json(row["swap_js"]).to_conventions()
                bnd_tenor = str(row["boundary_tenor"])
                return dtos.VolatilityMarketConventions(
                    libor_rate=libor, swap_rate=swp, boundary_tenor=bnd_tenor
                )


async def update_conventions(ccy: str, libor: str, swp: str, bnd_tenor: str) -> None:
    query = """
        UPDATE vol_conventions SET libor_rate = ?, swap_rate = ?, boundary_tenor = ?
        WHERE currency = ?
    """
    logger.info(f"updating database {ccy} conventions..")
    async with aiosqlite.connect(ctx.path) as db:
        await db.execute(query, (ccy, libor, swp, bnd_tenor))
        await db.commit()


if __name__ == "__main__":
    db_uuid = str(uuid.uuid4())[:8]
    ctx = Context(
        Path.home() / ".local" / "share" / "arbitui" / f"arbitui-{db_uuid}.db"
    )
    ctx.path.parent.mkdir(parents=True, exist_ok=True)

    async def run():
        await init_db(ctx)
        libor_rates = await get_libor_rates("USD", ctx)
        swap_rates = await get_swap_rates("USD", ctx)
        conventions = await get_conventions("USD", ctx)
        print(libor_rates)
        print()
        print(swap_rates)
        print()
        print(conventions)
        print()

    asyncio.run(run())

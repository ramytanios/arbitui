import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Dict

import aiosqlite
from loguru import logger

import dtos

CREATE_RATE_TABLE = """
    CREATE TABLE IF NOT EXISTS rate (
        currency TEXT NOT NULL, 
        name TEXT NOT NULL, 
        js JSON NOT NULL,
        PRIMARY KEY (currency, name)
    );
"""

CREATE_VOL_CONVENTIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS vol_conventions (
        currency TEXT PRIMARY KEY,
        libor_rate TEXT NOT NULL,
        swap_rate TEXT NOT NULL,
        boundary_tenor TEXT NOT NULL,

        FOREIGN KEY (currency, libor_rate) REFERENCES rate (currency, name),
        FOREIGN KEY (currency, swap_rate) REFERENCES rate (currency, name)
    );
"""

INIT_RATE_DATA = """
    INSERT OR IGNORE INTO rate VALUES 
        ('EUR', 'ESTR', '{"currency": "EUR", "tenor": "1D", "spot_lag": 0, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "ESTR"}, "type": "Libor"}'),
        ('EUR', 'ESTR12M', '{"currency": "EUR", "tenor": "12M", "spot_lag": 2, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "ESTR"}, "type": "Libor"}'),
        ('EUR', 'EURIBOR3M', '{"currency": "EUR", "tenor": "3M", "spot_lag": 2, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "EUR", "name": "EURIBOR3M"}, "type": "Libor"}'),
        ('EUR', 'ESTR10Y', '{"currency": "EUR", "tenor": "1Y", "spot_lag": 2, "floating_rate": "ESTR12M", "fixed_period": "12M", "fixed_day_counter": "Act360", "payment_delay": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "ESTR"}, "type": "SwapRate"}'),
        ('EUR', 'EURIBOR10Y', '{"currency": "EUR", "tenor": "1Y", "spot_lag": 2, "floating_rate": "EURIBOR3M", "fixed_period": "3M", "fixed_day_counter": "Act360", "payment_delay": 0, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "ESTR"}, "type": "SwapRate"}'),
        ('USD', 'SOFR', '{"currency": "USD", "tenor": "1D", "spot_lag": 0, "calendar": "world", "bd_convention": "Following", "day_counter": "Act360", "reset_curve": {"currency": "USD", "name": "SOFR"}, "type": "Libor"}'),
        ('USD', 'SOFR12M', '{"currency": "USD", "tenor": "12M", "spot_lag": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "day_counter": "Act360", "reset_curve": {"currency": "USD", "name": "SOFR"}, "type": "Libor"}'),
        ('USD', 'SOFR10Y', '{"currency": "USD", "tenor": "1Y", "spot_lag": 2, "floating_rate": "SOFR12M", "fixed_period": "12M", "fixed_day_counter": "Act360", "payment_delay": 2, "calendar": "world", "bd_convention": "ModifiedFollowing", "discount_curve": {"currency": "USD", "name": "SOFR"}, "type": "SwapRate"}');
"""

INIT_VOL_CONVENTIONS_DATA = """
    INSERT OR IGNORE INTO vol_conventions VALUES 
        ('EUR', 'ESTR', 'ESTR10Y', '1Y'),
        ('USD', 'SOFR', 'SOFR10Y', '1Y');
"""

INIT_DB_QUERY = f"""
    {CREATE_RATE_TABLE}
    {CREATE_VOL_CONVENTIONS_TABLE}
    {INIT_RATE_DATA}
    {INIT_VOL_CONVENTIONS_DATA}
"""


@dataclass
class Context:
    path: Path


@asynccontextmanager
async def get_db_connection(ctx: Context) -> AsyncGenerator[aiosqlite.Connection, None]:
    try:
        async with aiosqlite.connect(ctx.path) as db:
            yield db
    except aiosqlite.Error as e:
        logger.error(f"Database connection error: {e}")
        raise


async def init_db(ctx: Context) -> None:
    logger.info("initializing database ..")
    try:
        async with get_db_connection(ctx) as db:
            await db.executescript(INIT_DB_QUERY)
            await db.commit()
    except Exception as e:
        logger.error(f"failed to initialize db {e}")
        raise


async def get_rates_count(ctx: Context) -> int:
    try:
        async with get_db_connection(ctx) as db:
            async with db.execute("SELECT COUNT(*) FROM rate") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except aiosqlite.Error as e:
        logger.error(f"Failed to get rates count: {e}")
        raise


async def get_conventions_count(ctx: Context) -> int:
    try:
        async with get_db_connection(ctx) as db:
            async with db.execute("SELECT COUNT(*) FROM vol_conventions") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except aiosqlite.Error as e:
        logger.error(f"Failed to get conventions count: {e}")
        raise


GET_LIBOR_RATES_QUERY = """
    SELECT * FROM rate 
    WHERE currency = ? AND json_extract(js, '$.type') = 'Libor'
"""


async def get_libor_rates(ccy: str, ctx: Context) -> Dict[str, dtos.Libor]:
    logger.info(f"querying database for {ccy} libor rates")
    try:
        async with get_db_connection(ctx) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(GET_LIBOR_RATES_QUERY, (ccy,)) as cursor:
                rows = await cursor.fetchall()
                return {
                    str(row["name"]): dtos.Libor.model_validate_json(row["js"])
                    for row in rows
                }
    except aiosqlite.Error as e:
        logger.error(f"Failed to get libor rates for {ccy}: {e}")
        raise


GET_SWAP_RATES_QUERY = """
    SELECT * FROM rate 
    WHERE currency = ? AND json_extract(js, '$.type') = 'SwapRate'
"""


async def get_swap_rates(ccy: str, ctx: Context) -> Dict[str, dtos.SwapRate]:
    logger.info(f"querying database for {ccy} swap rates")
    try:
        async with get_db_connection(ctx) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(GET_SWAP_RATES_QUERY, (ccy,)) as cursor:
                rows = await cursor.fetchall()
                return {
                    str(row["name"]): dtos.SwapRate.model_validate_json(row["js"])
                    for row in rows
                }
    except aiosqlite.Error as e:
        logger.error(f"Failed to get swap rates for {ccy}: {e}")
        raise


GET_CONVENTIONS_QUERY = """
    SELECT vc.boundary_tenor, r1.name AS libor_name, r1.js AS libor_js, r2.name AS swap_name, r2.js AS swap_js 
    FROM vol_conventions AS vc
    JOIN rate AS r1 ON vc.currency = r1.currency AND vc.libor_rate = r1.name
    JOIN rate AS r2 ON vc.currency = r2.currency AND vc.swap_rate = r2.name
    WHERE vc.currency = ?
"""


async def get_conventions(ccy: str, ctx: Context) -> dtos.VolatilityMarketConventions:
    logger.info(f"querying database for {ccy} conventions..")
    try:
        async with get_db_connection(ctx) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(GET_CONVENTIONS_QUERY, (ccy,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise ValueError(f"Can't find {ccy} conventions")

                libor = (
                    str(row["libor_name"]),
                    dtos.Libor.model_validate_json(row["libor_js"]).to_conventions(),
                )
                swap_rate = (
                    str(row["swap_name"]),
                    dtos.SwapRate.model_validate_json(row["swap_js"]).to_conventions(),
                )
                boundary_tenor = str(row["boundary_tenor"])

                return dtos.VolatilityMarketConventions(
                    libor_rate=libor, swap_rate=swap_rate, boundary_tenor=boundary_tenor
                )
    except aiosqlite.Error as e:
        logger.error(f"Failed to get conventions for {ccy}: {e}")
        raise


UPDATE_CONVENTIONS_QUERY = """
    UPDATE vol_conventions 
    SET libor_rate = ?, swap_rate = ?, boundary_tenor = ?
    WHERE currency = ?
"""


async def update_conventions(
    ctx: Context, ccy: str, libor: str, swap_rate: str, boundary_tenor: str
) -> None:
    logger.info(f"updating database {ccy} conventions..")
    try:
        async with get_db_connection(ctx) as db:
            cursor = await db.execute(
                UPDATE_CONVENTIONS_QUERY, (libor, swap_rate, boundary_tenor, ccy)
            )
            if cursor.rowcount == 0:
                raise ValueError(f"No conventions found for currency {ccy}")
            await db.commit()
    except aiosqlite.Error as e:
        logger.error(f"Failed to update conventions for {ccy}: {e}")
        raise


if __name__ == "__main__":
    db_uuid = str(uuid.uuid4())[:8]
    ctx = Context(
        Path.home() / ".local" / "share" / "arbitui" / f"arbitui-{db_uuid}.db"
    )
    ctx.path.parent.mkdir(parents=True, exist_ok=True)

    async def run():
        try:
            await init_db(ctx)
            libor_rates = await get_libor_rates("USD", ctx)
            swap_rates = await get_swap_rates("USD", ctx)
            conventions = await get_conventions("USD", ctx)
            print(f"LIBOR rates: {libor_rates}")
            print(f"Swap rates: {swap_rates}")
            print(f"Conventions: {conventions}")
        except Exception as e:
            logger.error(f"Error in demo run: {e}")
            raise

    asyncio.run(run())

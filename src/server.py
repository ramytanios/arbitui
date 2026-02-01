import asyncio
import json
from asyncio.queues import Queue
from asyncio.taskgroups import TaskGroup
from contextlib import asynccontextmanager
from datetime import datetime
from json.decoder import JSONDecodeError
from typing import List, Tuple

import aiohttp
from loguru import logger
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

import db
import dtos
from handler import Handler
from message import (
    ArbitrageCheck,
    ArbitrageMatrix,
    ClientMsg,
    Conventions,
    GetArbitrageCheck,
    GetArbitrageMatrix,
    GetConventions,
    GetRates,
    GetVolSamples,
    LoadCube,
    Notification,
    Ping,
    Pong,
    Rates,
    ServerMsg,
    Severity,
    VolaCube,
    VolSamples,
    client_msg_adapter,
    server_msg_adapter,
)
from settings import settings


async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    t = datetime.now().date()  # TODO

    q_in = Queue[ClientMsg]()
    q_out = Queue[ServerMsg]()

    db_path = settings.home / "arbitui.db"
    ctx = db.Context(db_path)

    logger.info(f"initializing database at {db_path} ..")
    await db.init_db(ctx)

    async def recv_loop():
        try:
            async for js in ws.iter_json():
                msg = client_msg_adapter.validate_python(js)
                await q_in.put(msg)
        except WebSocketDisconnect:
            logger.exception("websocket disconnected")
            raise
        except ValidationError as e:
            logger.exception(f"failed to decode client message: {e}")
        except Exception as e:
            logger.exception(f"exception in receive loop: {e}")
            raise

    async def send_loop():
        try:
            while True:
                msg = await q_out.get()
                await ws.send_json(server_msg_adapter.dump_python(msg, mode="json"))
        except Exception as e:
            logger.exception(f"exception in send loop: {e}")
            raise

    async def get_conventions(ccy: str) -> Conventions:
        conventions = await db.get_conventions(ccy, ctx)
        return Conventions(currency=ccy, conventions=conventions)

    async def get_rates(ccy: str) -> Rates:
        libor_rates = await db.get_libor_rates(ccy, ctx)
        swap_rates = await db.get_swap_rates(ccy, ctx)
        return Rates(currency=ccy, libor_rates=libor_rates, swap_rates=swap_rates)

    async def get_arbitrage_matrix(
        ccy: str, vol: dtos.VolatilityCube, handler: Handler
    ) -> List[Tuple[dtos.Period, dtos.Period, dtos.ArbitrageCheck]]:
        if not settings.bulk_arbitrage_matrix:
            Q = Queue[Tuple[dtos.Period, dtos.Period, dtos.ArbitrageCheck]]()

            async def impl(tenor: dtos.Period, expiry: dtos.Period):
                check = await handler.arbitrage_check(t, vol, ccy, tenor, expiry)
                await Q.put((tenor, expiry, check))

            n = 0
            async with asyncio.TaskGroup() as tg:
                for tenor, surface in vol.cube.items():
                    for expiry in surface.surface:
                        tg.create_task(impl(tenor, expiry))
                        n += 1
            return [Q.get_nowait() for _ in range(n)]

        else:
            rsp = await handler.arbitrage_matrix(t, vol, ccy)
            return [(t, e, dtos.ArbitrageCheck(arbitrage=a)) for t, e, a in rsp.matrix]

    async def get_vol_sampling(
        ccy: str,
        vol: dtos.VolatilityCube,
        tenor: dtos.Period,
        expiry: dtos.Period,
        handler: Handler,
    ) -> dtos.VolSampling:
        return await handler.vol_sampling(t, vol, ccy, tenor, expiry)

    async def log_notify_error(msg: str):
        logger.exception(msg)
        await q_out.put(Notification(msg=msg, severity=Severity.ERROR))

    async def handle_client_msg(msg: ClientMsg, handler: Handler):
        match msg:
            case Ping():
                logger.info("ping received")
                await q_out.put(Pong())

            case LoadCube(file_path=path):
                try:
                    with open(path) as js:
                        cube_js = json.load(js)

                    ccy = cube_js["currency"]
                    vol = dtos.VolatilityCube.model_validate(cube_js["data"])

                except ValidationError:
                    await log_notify_error(f"failed to validate json in {path}")

                except JSONDecodeError:
                    await log_notify_error(f"failed to decode json in {path}")

                except Exception:
                    await log_notify_error(f"failed to load {path}")

                else:
                    await q_out.put(VolaCube(currency=ccy, cube=vol))

                    try:
                        conventions = await get_conventions(ccy)
                        await q_out.put(conventions)
                    except Exception:
                        await log_notify_error("failed to return conventions")

                    try:
                        rates = await get_rates(ccy)
                        await q_out.put(rates)
                    except Exception:
                        await log_notify_error("failed to return rates")

                    try:
                        matrix = await get_arbitrage_matrix(ccy, vol, handler)
                        await q_out.put(ArbitrageMatrix(currency=ccy, matrix=matrix))
                    except Exception:
                        await log_notify_error("failed to return arbitrage matrix")
                    else:
                        await q_out.put(
                            Notification(
                                msg="Arbitrage matrix constructed",
                                severity=Severity.INFORMATION,
                            )
                        )

                    tenor = list(vol.cube.keys())[0]
                    expiry = list(vol.cube[tenor].surface.keys())[0]
                    try:
                        samples = await get_vol_sampling(
                            ccy, vol, tenor, expiry, handler
                        )
                        await q_out.put(
                            VolSamples(
                                currency=ccy,
                                tenor=tenor,
                                expiry=expiry,
                                samples=samples,
                            )
                        )
                    except Exception:
                        await log_notify_error(
                            f"failed to return sampled data for rate underlying ({tenor},{expiry})"
                        )

            case GetConventions(currency=ccy):
                try:
                    msg_out = await get_conventions(ccy)
                    await q_out.put(msg_out)
                except Exception as e:
                    logger.exception(f"failed to handle conventions request: {e}")

            case GetRates(currency=ccy):
                try:
                    msg_out = await get_rates(ccy)
                    await q_out.put(msg_out)
                except Exception as e:
                    logger.exception(f"failed to handle rates request: {e}")

            case GetArbitrageMatrix(currency=ccy, vol_cube=vol):
                try:
                    matrix = await get_arbitrage_matrix(ccy, vol, handler)
                    msg_out = ArbitrageMatrix(currency=ccy, matrix=matrix)
                    await q_out.put(msg_out)
                except Exception as e:
                    logger.exception(f"failed to handle full arbitrage request: {e}")

            case GetArbitrageCheck(
                currency=ccy, vol_cube=vol, tenor=tenor, expiry=expiry
            ):
                try:
                    check = await handler.arbitrage_check(t, vol, ccy, tenor, expiry)
                    msg_out = ArbitrageCheck(
                        currency=ccy, tenor=tenor, expiry=expiry, check=check
                    )
                    await q_out.put(msg_out)
                except Exception as e:
                    logger.exception(f"failed to handle arbitrage request: {e}")

            case GetVolSamples(currency=ccy, vol_cube=vol, tenor=tenor, expiry=expiry):
                try:
                    samples = await get_vol_sampling(ccy, vol, tenor, expiry, handler)
                    msg_out = VolSamples(
                        currency=ccy, tenor=tenor, expiry=expiry, samples=samples
                    )
                    await q_out.put(msg_out)
                except Exception as e:
                    logger.exception(f"failed to handle vol samples request: {e}")

    async def handle_client_msg_loop():
        async with aiohttp.ClientSession() as session:
            handler = Handler(settings.rpc_url, session, ctx)
            try:
                while True:
                    msg = await q_in.get()
                    await handle_client_msg(msg, handler)
            except Exception as e:
                logger.exception(f"exception in handling client message: {e}")

    try:
        async with TaskGroup() as tg:
            tg.create_task(send_loop())
            tg.create_task(recv_loop())
            tg.create_task(handle_client_msg_loop())
    except* Exception as e:
        err = f"ws connection exception in task group: {e.exceptions}"
        logger.exception(err)
        await ws.close(reason=err)


@asynccontextmanager
async def lifespan(_):
    settings.home.mkdir(parents=True, exist_ok=True)
    logger.info(f"using settings {settings}")
    yield


app = Starlette(routes=[WebSocketRoute("/ws", websocket_endpoint)], lifespan=lifespan)

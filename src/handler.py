import uuid
from datetime import date
from typing import Type

from aiocache.decorators import cached
from loguru import logger
from pydantic import BaseModel

import db
import dtos
from lib import Method, RPCRequest, Socket
from settings import settings


class Handler:
    def __init__(self, socket: Socket, db_ctx: db.Context):
        self.socket = socket
        self.db_ctx = db_ctx

    async def _rpc_call[T: BaseModel](
        self,
        method: Method,
        params: dtos.ArbitrageParams
        | dtos.ArbitrageMatrixParams
        | dtos.VolSamplingParams,
        kls: Type[T],
    ) -> T:
        logger.info(f"rpc call method: {method.value}")
        request = RPCRequest(method=method.value, params=params, id=str(uuid.uuid4()))
        return await self.socket.call(request, kls)

    async def _market(self, volCube: dtos.VolatilityCube, ccy: str):
        vol_conventions = await db.get_conventions(ccy, self.db_ctx)
        libor_conventions = vol_conventions.libor_rate
        swap_conventions = vol_conventions.swap_rate
        floating_rate = (await db.get_libor_rates(ccy, self.db_ctx))[
            swap_conventions[1].floating_rate
        ]

        rates = {}
        rates[swap_conventions[1].floating_rate] = floating_rate

        curves = {}
        curves[libor_conventions[1].reset_curve.name] = dtos.ContinuousCompounding(
            rate=1.0 / 100  # TODO
        )
        curves[swap_conventions[1].discount_curve.name] = dtos.ContinuousCompounding(
            rate=1.0 / 100  # TODO
        )
        curves[floating_rate.reset_curve.name] = dtos.ContinuousCompounding(
            rate=1.0 / 100  # TODO
        )

        fixings = {}

        market = {}
        market[ccy] = dtos.CcyMarket(
            rates=rates,
            curves=curves,
            fixings=fixings,
            volatility=volCube,
            vol_conventions=dtos._VolatilityMarketConventions(
                libor_rate=libor_conventions[1],
                swap_rate=swap_conventions[1],
                boundary_tenor=vol_conventions.boundary_tenor,
            ),
        )

        calendars = {}
        calendars[libor_conventions[1].calendar] = dtos.Calendar(holidays=[])
        calendars[swap_conventions[1].calendar] = dtos.Calendar(holidays=[])
        calendars[floating_rate.calendar] = dtos.Calendar(holidays=[])

        static = dtos.Static(calendars=calendars)

        return market, static

    async def arbitrage_check(
        self,
        t: date,
        volCube: dtos.VolatilityCube,
        ccy: str,
        tenor: dtos.Period,
        expiry: dtos.Period,
    ) -> dtos.ArbitrageCheck:
        (market, static) = await self._market(volCube, ccy)

        params = dtos.ArbitrageParams(
            t_ref=t,
            market=market,
            static=static,
            currency=ccy,
            tenor=tenor,
            expiry=expiry,
        )

        return await self._rpc_call(Method.ARBITRAGE, params, dtos.ArbitrageCheck)

    async def arbitrage_matrix(
        self,
        t: date,
        volCube: dtos.VolatilityCube,
        ccy: str,
    ) -> dtos.ArbitrageMatrix:
        (market, static) = await self._market(volCube, ccy)

        params = dtos.ArbitrageMatrixParams(
            t_ref=t, market=market, static=static, currency=ccy
        )

        return await self._rpc_call(
            Method.ARBITRAGE_MATRIX, params, dtos.ArbitrageMatrix
        )

    @cached(ttl=settings.vol_sampling_cache_ttl, noself=True)
    async def vol_sampling(
        self,
        t: date,
        volCube: dtos.VolatilityCube,
        ccy: str,
        tenor: dtos.Period,
        expiry: dtos.Period,
    ) -> dtos.VolSampling:
        (market, static) = await self._market(volCube, ccy)

        params = dtos.VolSamplingParams(
            t_ref=t,
            market=market,
            static=static,
            currency=ccy,
            tenor=tenor,
            expiry=expiry,
            n_samples_middle=100,
            n_samples_tail=10,
            n_stdvs_tail=0,
        )

        return await self._rpc_call(Method.VOL_SAMPLING, params, dtos.VolSampling)

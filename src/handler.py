from datetime import date

from aiohttp import ClientSession

import db
import dtos
import lib


class Handler:
    def __init__(self, rpc_url: str, http_session: ClientSession, db_ctx: db.Context):
        self._rpc_url = rpc_url
        self._http_session = http_session
        self._db_ctx = db_ctx

    async def _market(self, volCube: dtos.VolatilityCube, ccy: str):
        vol_conventions = await db.get_conventions(ccy, self._db_ctx)
        libor_conventions = vol_conventions.libor_rate
        swap_conventions = vol_conventions.swap_rate
        floating_rate = (await db.get_libor_rates(ccy, self._db_ctx))[
            swap_conventions[1].floating_rate
        ]

        rates = {}
        rates[swap_conventions[1].floating_rate] = floating_rate

        curves = {}
        curves[libor_conventions[1].reset_curve.name] = dtos.ContinuousCompounding(
            rate=0.9
        )
        curves[swap_conventions[1].discount_curve.name] = dtos.ContinuousCompounding(
            rate=0.9
        )
        curves[floating_rate.reset_curve.name] = dtos.ContinuousCompounding(rate=0.9)

        fixings = {}

        market = {}
        market[ccy] = dtos.CcyMarket(
            rates=rates,
            curves=curves,
            fixings=fixings,
            volatility=volCube,
            vol_conventions=dtos._VolatilityMarketConventions(
                libor_rate=vol_conventions.libor_rate[1],
                swap_rate=vol_conventions.swap_rate[1],
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
        tenor: str,
        expiry: str,
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

        return await lib.arbitrage_check(params, self._http_session, self._rpc_url)

    async def vol_sampling(
        self,
        t: date,
        volCube: dtos.VolatilityCube,
        ccy: str,
        tenor: str,
        expiry: str,
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
            n_stdvs_tail=4,
        )

        return await lib.vol_sampling(params, self._http_session, self._rpc_url)

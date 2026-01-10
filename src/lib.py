import asyncio
import uuid
from datetime import date
from typing import Literal, Optional, Type

from aiohttp import ClientSession
from pydantic import BaseModel
from rich import print_json

import dtos
import lib


class RpcRequest(BaseModel):
    method: str
    params: dtos.ArbitrageParams | dtos.VolSamplingParams
    id: str
    jsonrpc: Literal["2.0"] = "2.0"


class Error(BaseModel):
    code: int
    message: str
    data: Optional[dict]


class RpcResponse(BaseModel):
    result: Optional[dict]
    error: Optional[Error]
    id: Optional[str]
    jsonrpc: Literal["2.0"] = "2.0"


async def _rpc_call[T: BaseModel](
    method: str,
    params: BaseModel,
    session: ClientSession,
    remote_url: str,
    kls: Type[T],
) -> T:
    request = RpcRequest(method=method, params=params, id=str(uuid.uuid4()))
    json = request.model_dump(by_alias=True, mode="json")
    async with session.post(remote_url, json=json) as response:
        js = await response.json()
        rsp = RpcResponse.model_validate(js)
        if rsp.error:
            raise Exception(f"rpc error: {rsp.error.message}")
        if rsp.result is None:
            raise Exception("rpc missing `result` in response")
        return kls.model_validate(rsp.result)


async def arbitrage_check(
    params: dtos.ArbitrageParams, session: ClientSession, remote_url: str
) -> dtos.ArbitrageCheck:
    rsp = await _rpc_call("arbitrage", params, session, remote_url, dtos.ArbitrageCheck)
    return rsp


async def vol_sampling(
    params: dtos.VolSamplingParams, session: ClientSession, remote_url: str
) -> dtos.VolSampling:
    rsp = await _rpc_call("volsampling", params, session, remote_url, dtos.VolSampling)
    return rsp


if __name__ == "__main__":
    remote_url = "http://localhost:8090/rpc"

    arb_params = dtos.ArbitrageParams(
        t_ref=date.fromisoformat("2025-10-12"),
        currency="USD",
        market={
            "USD": dtos.CcyMarket(
                rates={
                    "LIBOR_RATE": dtos.Libor(
                        currency="USD",
                        tenor="3M",
                        spot_lag=2,
                        day_counter=dtos.DayCounter.ACT360,
                        calendar="NO_HOLIDAYS",
                        reset_curve=dtos.Curve(currency="USD", name="SINGLE_CURVE"),
                        bd_convention=dtos.BusinessDayConvention.MODIFIED_FOLLOWING,
                    )
                },
                curves={"SINGLE_CURVE": dtos.ContinuousCompounding(rate=0.02)},
                fixings={},
                volatility=dtos.VolatilityCube(
                    unit=dtos.VolUnit.BpPerYear,
                    cube={
                        "3M": dtos.VolatilitySurface(
                            surface={
                                "1Y": dtos.VolatilitySkew(
                                    skew=[
                                        (-0.0200, 100.0),
                                        (-0.0100, 80.0),
                                        (-0.0050, 72.0),
                                        (-0.0025, 70.0),
                                        (0.0000, 69.0),
                                        (0.0025, 71.0),
                                        (0.0050, 74.0),
                                        (0.0100, 90.0),
                                        (0.0200, 93.0),
                                    ]
                                )
                            }
                        )
                    },
                ),
                vol_conventions=dtos.VolatilityMarketConventions(
                    boundary_tenor="10Y",
                    libor_rate=dtos.LiborConventions(
                        currency="USD",
                        spot_lag=2,
                        day_counter=dtos.DayCounter.ACT360,
                        calendar="NO_HOLIDAYS",
                        reset_curve=dtos.Curve(currency="USD", name="SINGLE_CURVE"),
                        bd_convention=dtos.BusinessDayConvention.MODIFIED_FOLLOWING,
                    ),
                    swap_rate=dtos.SwapRateConventions(
                        spot_lag=2,
                        payment_delay=0,
                        fixed_period="3M",
                        floating_rate="LIBOR_RATE",
                        fixed_day_counter=dtos.DayCounter.ACT360,
                        calendar="NO_HOLIDAYS",
                        bd_convention=dtos.BusinessDayConvention.MODIFIED_FOLLOWING,
                        stub=dtos.StubConvention.SHORT,
                        direction=dtos.Direction.BACKWARD,
                        discount_curve=dtos.Curve(currency="USD", name="SINGLE_CURVE"),
                    ),
                ),
            )
        },
        static=dtos.Static(calendars={"NO_HOLIDAYS": dtos.Calendar(holidays=[])}),
        expiry="10Y",
        tenor="3M",
    )

    sampling_params = dtos.VolSamplingParams(
        t_ref=date.fromisoformat("2025-10-12"),
        currency="USD",
        market={
            "USD": dtos.CcyMarket(
                rates={
                    "LIBOR_RATE": dtos.Libor(
                        currency="USD",
                        tenor="3M",
                        spot_lag=2,
                        day_counter=dtos.DayCounter.ACT360,
                        calendar="NO_HOLIDAYS",
                        reset_curve=dtos.Curve(currency="USD", name="SINGLE_CURVE"),
                        bd_convention=dtos.BusinessDayConvention.MODIFIED_FOLLOWING,
                    )
                },
                curves={"SINGLE_CURVE": dtos.ContinuousCompounding(rate=0.02)},
                fixings={},
                volatility=dtos.VolatilityCube(
                    unit=dtos.VolUnit.BpPerYear,
                    cube={
                        "3M": dtos.VolatilitySurface(
                            surface={
                                "1Y": dtos.VolatilitySkew(
                                    skew=[
                                        (-0.0200, 100.0),
                                        (-0.0100, 80.0),
                                        (-0.0050, 72.0),
                                        (-0.0025, 70.0),
                                        (0.0000, 69.0),
                                        (0.0025, 71.0),
                                        (0.0050, 74.0),
                                        (0.0100, 90.0),
                                        (0.0200, 93.0),
                                    ]
                                )
                            }
                        )
                    },
                ),
                vol_conventions=dtos.VolatilityMarketConventions(
                    boundary_tenor="10Y",
                    libor_rate=dtos.LiborConventions(
                        currency="USD",
                        spot_lag=2,
                        day_counter=dtos.DayCounter.ACT360,
                        calendar="NO_HOLIDAYS",
                        reset_curve=dtos.Curve(currency="USD", name="SINGLE_CURVE"),
                        bd_convention=dtos.BusinessDayConvention.MODIFIED_FOLLOWING,
                    ),
                    swap_rate=dtos.SwapRateConventions(
                        spot_lag=2,
                        payment_delay=0,
                        fixed_period="3M",
                        floating_rate="LIBOR_RATE",
                        fixed_day_counter=dtos.DayCounter.ACT360,
                        calendar="NO_HOLIDAYS",
                        bd_convention=dtos.BusinessDayConvention.MODIFIED_FOLLOWING,
                        stub=dtos.StubConvention.SHORT,
                        direction=dtos.Direction.BACKWARD,
                        discount_curve=dtos.Curve(currency="USD", name="SINGLE_CURVE"),
                    ),
                ),
            )
        },
        static=dtos.Static(calendars={"NO_HOLIDAYS": dtos.Calendar(holidays=[])}),
        expiry="10Y",
        tenor="3M",
        n_samples=10,
        n_stdvs=5,
    )

    async def run():
        async with ClientSession() as session:
            arb = await lib.arbitrage_check(arb_params, session, remote_url)
            print_json(arb.model_dump_json())

            sampling = await lib.vol_sampling(sampling_params, session, remote_url)
            print_json(sampling.model_dump_json())

    asyncio.run(run())

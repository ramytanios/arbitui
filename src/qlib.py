import uuid
from dataclasses import asdict
from typing import Literal

from aiohttp import ClientSession
from pydantic.dataclasses import dataclass

import dtos


@dataclass
class RpcRequest:
    method: str
    params: dtos.ArbitrageParams | dtos.VolSamplingParams
    id: str
    jsonrpc: Literal["2.0"] = "2.0"


@dataclass
class Error:
    code: int
    message: str
    data: dict | None


@dataclass
class RpcResponse:
    result: dict | None
    error: Error | None
    id: str | None
    jsonrpc: Literal["2.0"] = "2.0"


@dataclass
class LeftAsymptotic:
    pass


@dataclass
class RightAsymptotic:
    pass


@dataclass
class Density:
    left_strike: float
    right_strike: float


type Arbitrage = LeftAsymptotic | RightAsymptotic | Density


@dataclass
class ArbitrageCheck:
    arbitrage: None | Arbitrage


@dataclass
class VolSampling:
    quoted_strikes: list[float]
    quoted_vols: list[float]
    quoted_pdf: list[float]
    strikes: list[float]
    vols: list[float]
    pdf: list[float]


async def arbitrage_check(
    params: dtos.ArbitrageParams, session: ClientSession, remote_url: str
) -> ArbitrageCheck:
    request = RpcRequest("arbitrage", params, str(uuid.uuid4()))
    data = asdict(request)
    async with session.post(remote_url, json=data) as rsp:
        js = await rsp.json()
        return ArbitrageCheck(**js)


async def vol_sampling(
    params: dtos.VolSamplingParams, session: ClientSession, remote_url: str
) -> VolSampling:
    request = RpcRequest("volsampling", params, str(uuid.uuid4()))
    data = asdict(request)
    async with session.post(remote_url, json=data) as rsp:
        js = await rsp.json()
        return VolSampling(**js)

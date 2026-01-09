import uuid
from dataclasses import asdict
from typing import Literal, Optional

from aiohttp import ClientSession
from pydantic.dataclasses import dataclass

import dtos


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
    arbitrage: Optional[Arbitrage]


@dataclass
class VolSampling:
    quoted_strikes: list[float]
    quoted_vols: list[float]
    quoted_pdf: list[float]
    strikes: list[float]
    vols: list[float]
    pdf: list[float]


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
    data: Optional[dict]


@dataclass
class RpcResponse:
    result: Optional[dict]
    error: Optional[Error]
    id: Optional[str]
    jsonrpc: Literal["2.0"] = "2.0"


async def arbitrage_check(
    params: dtos.ArbitrageParams, session: ClientSession, remote_url: str
) -> ArbitrageCheck:
    request = RpcRequest("arbitrage", params, str(uuid.uuid4()))
    data = asdict(request)
    async with session.post(remote_url, json=data) as response:
        js = await response.json()
        rsp = RpcResponse(**js)
        if rsp.error:
            raise Exception(f"rpc error: {rsp.error.message}")
        if rsp.result is None:
            raise Exception("rpc missing `result` in response")
        return ArbitrageCheck(**rsp.result)


async def vol_sampling(
    params: dtos.VolSamplingParams, session: ClientSession, remote_url: str
) -> VolSampling:
    request = RpcRequest("volsampling", params, str(uuid.uuid4()))
    data = asdict(request)
    async with session.post(remote_url, json=data) as response:
        js = await response.json()
        rsp = RpcResponse(**js)
        if rsp.error:
            raise Exception(f"rpc error: {rsp.error.message}")
        if rsp.result is None:
            raise Exception("rpc missing `result` in response")
        return VolSampling(**rsp.result)

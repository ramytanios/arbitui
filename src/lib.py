import uuid
from typing import Literal, Optional, Type

from aiohttp import ClientSession
from loguru import logger
from pydantic import BaseModel

import dtos


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
    params: dtos.ArbitrageParams | dtos.VolSamplingParams,
    session: ClientSession,
    remote_url: str,
    kls: Type[T],
) -> T:
    logger.info(f"rpc call method: {method}")
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

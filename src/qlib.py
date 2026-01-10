import uuid
from typing import Literal, Optional, Type

from aiohttp import ClientSession
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


async def rpc_call[T](
    method: str,
    params: BaseModel,
    session: ClientSession,
    remote_url: str,
    kls: Type[T],
) -> T:
    request = RpcRequest(method=method, params=params, id=str(uuid.uuid4()))
    json = RpcRequest.model_dump(request, by_alias=True)
    async with session.post(remote_url, json=json) as response:
        js = await response.json()
        rsp = RpcResponse.model_validate(js)
        if rsp.error:
            raise Exception(f"rpc error: {rsp.error.message}")
        if rsp.result is None:
            raise Exception("rpc missing `result` in response")
        return kls(**rsp.result)


async def arbitrage_check(
    params: dtos.ArbitrageParams, session: ClientSession, remote_url: str
) -> dtos.ArbitrageCheck:
    rsp = await rpc_call("arbitrage", params, session, remote_url, dtos.ArbitrageCheck)
    return rsp


async def vol_sampling(
    params: dtos.VolSamplingParams, session: ClientSession, remote_url: str
) -> dtos.VolSampling:
    rsp = await rpc_call("volsampling", params, session, remote_url, dtos.VolSampling)
    return rsp

import asyncio
from asyncio import Future
from asyncio.locks import Lock, Semaphore
from asyncio.streams import StreamReader, StreamWriter
from asyncio.taskgroups import TaskGroup
from enum import Enum
from typing import Dict, Literal, Optional, Type

from loguru import logger
from pydantic import BaseModel

import dtos
from settings import settings


class Method(Enum):
    PRICE = "price"
    VOL_SAMPLING = "vol-sampling"
    ARBITRAGE = "arbitrage"
    ARBITRAGE_MATRIX = "arbitrage-matrix"


class RPCRequest(BaseModel):
    method: Method
    params: dtos.ArbitrageParams | dtos.ArbitrageMatrixParams | dtos.VolSamplingParams
    id: str
    jsonrpc: Literal["2.0"] = "2.0"


class Error(BaseModel):
    code: int
    message: str
    data: Optional[dict]


class RPCResponse(BaseModel):
    result: Optional[dict]
    error: Optional[Error]
    id: Optional[str]
    jsonrpc: Literal["2.0"] = "2.0"


class Socket:
    def __init__(self, path: str):
        self._path = path
        self._reader: Optional[StreamReader] = None
        self._writer: Optional[StreamWriter] = None
        self._lock: Lock = Lock()
        self._sem: Semaphore = Semaphore(settings.max_requests_in_flight)
        self._pending: Dict[str, Future] = {}

    async def register_and_send(self, request: RPCRequest) -> None:
        if writer := self._writer:
            async with self._sem:
                fut = asyncio.get_running_loop().create_future()
                async with self._lock:
                    self._pending[request.id] = fut
                js = RPCRequest.model_dump_json(request, by_alias=True) + "\n"
                line = js.encode("utf-8")
                writer.write(line)
                await writer.drain()

    async def recv_loop(self) -> None:
        if reader := self._reader:
            while True:
                line = await reader.readline()
                rsp = RPCResponse.model_validate_json(line)
                if (id := rsp.id) is not None:
                    fut = self._pending.pop(id, None)
                    if fut and not fut.done():
                        if rsp.error is not None or rsp.result is None:
                            err = (
                                rsp.error.message
                                if rsp.error is not None
                                else "response missing `result`"
                            )
                            fut.set_exception(RuntimeError(err))
                        else:
                            fut.set_result(rsp.result)

    async def __aenter__(self):
        self._reader, self._writer = await asyncio.open_unix_connection(path=self._path)
        tg = TaskGroup()
        await tg.__aenter__()
        tg.create_task(self.recv_loop())
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            logger.opt()
            logger.exception(
                f"exception in context: {exc_type.__name__}: {exc}", traceback=tb
            )
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    async def call[T: BaseModel](self, request: RPCRequest, kls: Type[T]) -> T:
        await self.register_and_send(request)
        fut = self._pending.get(request.id)

        if fut is None:
            # this indicates a bug/race: send() didn't register, or reader removed it early.
            raise RuntimeError(f"Missing pending Future for request id={request.id}")

        try:
            fut_res = await asyncio.wait_for(fut, settings.socket_timeout)
            return kls.model_validate(fut_res)
        except Exception as e:
            logger.exception(f"fut {request.id} completed with exception: {e}")
            raise

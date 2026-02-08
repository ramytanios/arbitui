import asyncio
from asyncio.streams import StreamReader, StreamWriter
from enum import Enum
from typing import Literal, Optional

from loguru import logger
from pydantic import BaseModel

import dtos


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
        self.path = path
        self.read: Optional[StreamReader] = None
        self.write: Optional[StreamWriter] = None

    async def __aenter__(self):
        self.read, self.write = await asyncio.open_unix_connection(path=self.path)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            logger.opt()
            logger.exception(
                f"exception in context: {exc_type.__name__}: {exc}", traceback=tb
            )

        if self.write is not None:
            self.write.close()
            await self.write.wait_closed()
        self.read = None
        self.write = None

    async def call(self, request: RPCRequest) -> RPCResponse:
        pass

from enum import Enum
from typing import Annotated, List, Literal, Tuple, Union

from pydantic import BaseModel, Field
from pydantic.type_adapter import TypeAdapter

import dtos


class Ping(BaseModel):
    type: Literal["ping"] = "ping"


class LoadCube(BaseModel):
    file_path: str
    type: Literal["load_cube"] = "load_cube"


class GetConventions(BaseModel):
    currency: str
    type: Literal["get_conventions"] = "get_conventions"


class GetRates(BaseModel):
    currency: str
    type: Literal["get_rates"] = "get_rates"


class GetArbitrageMatrix(BaseModel):
    currency: str
    vol_cube: dtos.VolatilityCube
    type: Literal["get_arbitrage_matrix"] = "get_arbitrage_matrix"


class GetArbitrageCheck(BaseModel):
    currency: str
    vol_cube: dtos.VolatilityCube
    tenor: str
    expiry: str
    type: Literal["get_arbitrage_check"] = "get_arbitrage_check"


class GetVolSamples(BaseModel):
    currency: str
    vol_cube: dtos.VolatilityCube
    tenor: str
    expiry: str
    type: Literal["get_vol_samples"] = "get_vol_samples"


type ClientMsg = Annotated[
    Union[
        Ping,
        LoadCube,
        GetConventions,
        GetRates,
        GetArbitrageMatrix,
        GetArbitrageCheck,
        GetVolSamples,
    ],
    Field(discriminator="type"),
]


class Pong(BaseModel):
    type: Literal["pong"] = "pong"


class VolaCube(BaseModel):
    currency: str
    cube: dtos.VolatilityCube
    type: Literal["vola_cube"] = "vola_cube"


class Conventions(BaseModel):
    currency: str
    conventions: dtos.VolatilityMarketConventions
    type: Literal["conventions"] = "conventions"


class Rates(BaseModel):
    currency: str
    libor_rates: dict[str, dtos.Libor]
    swap_rates: dict[str, dtos.SwapRate]
    type: Literal["rates"] = "rates"


class ArbitrageMatrix(BaseModel):
    currency: str
    matrix: List[Tuple[str, str, dtos.ArbitrageCheck]]
    type: Literal["arbitrage_matrix"] = "arbitrage_matrix"


class ArbitrageCheck(BaseModel):
    currency: str
    tenor: str
    expiry: str
    check: dtos.ArbitrageCheck
    type: Literal["arbitrage_check"] = "arbitrage_check"


class VolSamples(BaseModel):
    currency: str
    tenor: str
    expiry: str
    samples: dtos.VolSampling
    type: Literal["vol_samples"] = "vol_samples"


class Severity(Enum):
    INFORMATION = "information"
    ERROR = "error"
    WARNING = "warning"

    def to_textual(self) -> Literal["error", "warning", "information"]:
        match self.value:
            case Severity.ERROR:
                return "error"
            case Severity.WARNING:
                return "warning"
            case Severity.INFORMATION:
                return "information"
            case _:
                raise


class Notification(BaseModel):
    msg: str
    severity: Severity
    type: Literal["notification"] = "notification"


type ServerMsg = Annotated[
    Union[
        Pong,
        VolaCube,
        Conventions,
        Rates,
        ArbitrageMatrix,
        ArbitrageCheck,
        VolSamples,
        Notification,
    ],
    Field(discriminator="type"),
]


server_msg_adapter: TypeAdapter[ServerMsg] = TypeAdapter(ServerMsg)

client_msg_adapter: TypeAdapter[ClientMsg] = TypeAdapter(ClientMsg)

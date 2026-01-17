from typing import Annotated, Literal, Tuple, Union

from pydantic import BaseModel, Field

import dtos


class Ping(BaseModel):
    type: Literal["ping"] = "ping"


class GetConventions(BaseModel):
    currency: str
    type: Literal["get_conventions"] = "get_conventions"


class GetRates(BaseModel):
    currency: str
    type: Literal["get_rates"] = "get_rates"


class GetFullArbitrageCheck(BaseModel):
    currency: str
    vol_cube: dtos.VolatilityCube
    type: Literal["get_full_arbitrage_check"] = "get_full_arbitrage_check"


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
        GetConventions,
        GetRates,
        GetFullArbitrageCheck,
        GetArbitrageCheck,
        GetVolSamples,
    ],
    Field(discriminator="type"),
]


class Pong(BaseModel):
    type: Literal["pong"] = "pong"


class Conventions(BaseModel):
    currency: str
    conventions: dtos.VolatilityMarketConventions
    type: Literal["conventions"] = "conventions"


class Rates(BaseModel):
    currency: str
    libor_rates: dict[str, dtos.Libor]
    swap_rates: dict[str, dtos.SwapRate]
    type: Literal["rates"] = "rates"


class FullArbitrageCheck(BaseModel):
    currency: str
    checks: dict[Tuple[str, str], dtos.ArbitrageCheck]
    type: Literal["full_arbitrage_check"] = "full_arbitrage_check"


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


type ServerMsg = Annotated[
    Union[Pong, Conventions, Rates, FullArbitrageCheck, ArbitrageCheck, VolSamples],
    Field(discriminator="type"),
]

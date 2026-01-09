from datetime import date
from enum import Enum, auto
from typing import Literal, Tuple

from pydantic.dataclasses import dataclass


@dataclass
class Curve:
    name: str
    ccy: str


class Direction(Enum):
    FORWARD = auto()
    BACKWARD = auto()


class StubConvention(Enum):
    SHORT = auto()
    LONG = auto()


class BusinessDayConvention(Enum):
    FOLLOWING = auto()
    PRECEDING = auto()
    MODIFIED_FOLLOWING = auto()


class DayCounter(Enum):
    ACT365 = auto()
    ACT360 = auto()


@dataclass
class Libor:
    currency: str
    tenor: str
    spot_lag: int
    day_counter: DayCounter
    calendar: str
    reset_curve: Curve
    bd_convention: BusinessDayConvention
    type: Literal["libor"] = "libor"


@dataclass
class SwapRate:
    tenor: str
    spot_lag: int
    payment_delay: int
    fixed_period: int
    floating_rate: str
    fixed_day_counter: DayCounter
    calendar: str
    bd_convention: BusinessDayConvention
    stub: StubConvention
    direction: Direction
    discount_curve: Curve


@dataclass
class CompoundedSwapRate:
    tenor: str
    spot_lag: int
    payment_delay: int
    fixed_period: str
    floating_rate: str
    floating_period: str
    fixed_day_counter: DayCounter
    calendar: str
    bd_convention: BusinessDayConvention
    stub: StubConvention
    direction: Direction
    discount_curve: Curve


type Underlying = Libor | SwapRate | CompoundedSwapRate


class OptionType(Enum):
    CALL = auto()
    PUT = auto()


class Annuity(Enum):
    CASH = auto()
    PHYSICAL = auto()


@dataclass
class Caplet:
    rate: str
    fixing_at: date
    start_at: date
    end_at: date
    payment_at: date
    payment_ccy: str
    strike: float
    discount_curve: Curve
    option_type: OptionType


@dataclass
class Swaption:
    rate: str
    fixing_at: date
    strike: float
    option_type: OptionType
    annuity: Annuity
    discount_curve: Curve


@dataclass
class BackwardLookingCaplet:
    start_at: date
    end_at: date
    rate: str
    payment_ccy: str
    payment_at: date
    strike: float
    option_type: OptionType
    discount_curve: Curve
    stub: StubConvention
    direction: Direction


type Payoff = Caplet | Swaption | BackwardLookingCaplet


@dataclass
class Discounts:
    discounts: list[Tuple[date, float]]


@dataclass
class ContinuousCompounding:
    rate: float


type YieldCurve = Discounts | ContinuousCompounding


@dataclass
class Fixing:
    t: date
    value: float


@dataclass
class VolatilitySkew:
    skew: list[Tuple[float, float]]


@dataclass
class VolatilitySurface:
    surface: dict[str, VolatilitySkew]


@dataclass
class VolatilityCube:
    cube: dict[str, VolatilitySurface]


@dataclass
class LiborConventions:
    currency: str
    spot_lag: int
    day_counter: DayCounter
    calendar: str
    reset_curve: Curve
    bd_convention: BusinessDayConvention


@dataclass
class SwapRateConventions:
    spot_lag: int
    payment_delay: int
    fixed_period: str
    floating_rate: str
    fixed_day_counter: DayCounter
    calendar: str
    bd_convention: BusinessDayConvention
    stub: StubConvention
    direction: Direction
    discount_curve: Curve


@dataclass
class VolatilityMarketConventions:
    boundary_tenor: str
    libor_rate: LiborConventions
    swap_rate: SwapRateConventions


@dataclass
class CcyMarket:
    rates: dict[str, Underlying]
    curves: dict[str, YieldCurve]
    fixings: dict[str, list[Fixing]]
    volatility: VolatilityCube
    vol_conventions: VolatilityMarketConventions


@dataclass
class Calendar:
    holidays: list[date]


@dataclass
class Static:
    calendars: dict[str, Calendar]


@dataclass
class ArbitrageParams:
    t: date
    market: dict[str, CcyMarket]
    static: Static
    ccy: str
    tenor: str
    expiry: str


@dataclass
class VolSamplingParams:
    t: date
    market: dict[str, CcyMarket]
    static: Static
    ccy: str
    tenor: str
    expiry: str
    n_samples: int
    n_stdvs: int

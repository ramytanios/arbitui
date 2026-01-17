from datetime import datetime
from datetime import date
from enum import Enum, auto
from typing import Literal, Optional, Tuple

from pydantic.config import ConfigDict
from pydantic.main import BaseModel
from pydantic.v1.utils import to_lower_camel


class Dto(BaseModel):
    model_config = ConfigDict(alias_generator=to_lower_camel, validate_by_name=True)


class Curve(Dto):
    name: str
    currency: str


class Direction(Enum):
    FORWARD = "Forward"
    BACKWARD = "Backward"


class StubConvention(Enum):
    SHORT = "Short"
    LONG = "Long"


class BusinessDayConvention(Enum):
    FOLLOWING = "Following"
    PRECEDING = "Preceding"
    MODIFIED_FOLLOWING = "ModifiedFollowing"


class DayCounter(Enum):
    ACT360 = "Act360"
    ACT365 = "Act365"


class Libor(Dto):
    currency: str
    tenor: str
    spot_lag: int
    day_counter: DayCounter
    calendar: str
    reset_curve: Curve
    bd_convention: BusinessDayConvention
    type: Literal["Libor"] = "Libor"

    def to_conventions(self) -> "LiborConventions":
        return LiborConventions(
            currency=self.currency,
            spot_lag=self.spot_lag,
            day_counter=self.day_counter,
            calendar=self.calendar,
            reset_curve=self.reset_curve,
            bd_convention=self.bd_convention,
        )


class SwapRate(Dto):
    tenor: str
    spot_lag: int
    payment_delay: int
    fixed_period: str
    floating_rate: str
    fixed_day_counter: DayCounter
    calendar: str
    bd_convention: BusinessDayConvention
    discount_curve: Curve
    stub: StubConvention = StubConvention.LONG
    direction: Direction = Direction.BACKWARD
    type: Literal["SwapRate"] = "SwapRate"

    def to_conventions(self) -> "SwapRateConventions":
        return SwapRateConventions(
            spot_lag=self.spot_lag,
            payment_delay=self.payment_delay,
            fixed_period=self.fixed_period,
            floating_rate=self.floating_rate,
            fixed_day_counter=self.fixed_day_counter,
            calendar=self.calendar,
            bd_convention=self.bd_convention,
            stub=self.stub,
            direction=self.direction,
            discount_curve=self.discount_curve,
        )


class CompoundedSwapRate(Dto):
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
    type: Literal["CompoundedSwapRate"] = "CompoundedSwapRate"


type Underlying = Libor | SwapRate | CompoundedSwapRate


class OptionType(Enum):
    CALL = auto()
    PUT = auto()


class Annuity(Enum):
    CASH = auto()
    PHYSICAL = auto()


class Caplet(Dto):
    rate: str
    fixing_at: date
    start_at: date
    end_at: date
    payment_at: date
    payment_ccy: str
    strike: float
    discount_curve: Curve
    option_type: OptionType


class Swaption(Dto):
    rate: str
    fixing_at: date
    strike: float
    option_type: OptionType
    annuity: Annuity
    discount_curve: Curve


class BackwardLookingCaplet(Dto):
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


class Discounts(Dto):
    discounts: list[Tuple[date, float]]
    type: Literal["Discounts"] = "Discounts"


class ContinuousCompounding(Dto):
    rate: float
    type: Literal["ContinuousCompounding"] = "ContinuousCompounding"


type YieldCurve = Discounts | ContinuousCompounding


class Fixing(Dto):
    t: date
    value: float


class VolatilitySkew(Dto):
    skew: list[Tuple[float, float]]


class VolatilitySurface(Dto):
    surface: dict[str, VolatilitySkew]


class VolUnit(Enum):
    BpPerYear = "BpPerYear"


class VolatilityCube(Dto):
    unit: VolUnit
    cube: dict[str, VolatilitySurface]


class LiborConventions(Dto):
    currency: str
    spot_lag: int
    day_counter: DayCounter
    calendar: str
    reset_curve: Curve
    bd_convention: BusinessDayConvention


class SwapRateConventions(Dto):
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


class VolatilityMarketConventions(Dto):
    libor: LiborConventions
    swap: SwapRateConventions
    boundary_tenor: str


class CcyMarket(Dto):
    rates: dict[str, Underlying]
    curves: dict[str, YieldCurve]
    fixings: dict[str, list[Fixing]]
    volatility: VolatilityCube
    vol_conventions: VolatilityMarketConventions


class Calendar(Dto):
    holidays: list[date]


class Static(Dto):
    calendars: dict[str, Calendar]


class ArbitrageParams(Dto):
    t_ref: datetime
    market: dict[str, CcyMarket]
    static: Static
    currency: str
    tenor: str
    expiry: str


class VolSamplingParams(Dto):
    t_ref: datetime
    market: dict[str, CcyMarket]
    static: Static
    currency: str
    tenor: str
    expiry: str
    n_samples: int
    n_stdvs: int


class LeftAsymptotic(Dto):
    type: Literal["LeftAsymptotic"] = "LeftAsymptotic"


class RightAsymptotic(Dto):
    type: Literal["RightAsymptotic"] = "RightAsymptotic"


class Density(Dto):
    between: Tuple[float, float]
    type: Literal["Density"] = "Density"


type Arbitrage = LeftAsymptotic | RightAsymptotic | Density


class ArbitrageCheck(Dto):
    arbitrage: Optional[Arbitrage]


class VolSampling(Dto):
    quoted_strikes: list[float]
    quoted_vols: list[float]
    quoted_pdf: list[float]
    strikes: list[float]
    vols: list[float]
    pdf: list[float]

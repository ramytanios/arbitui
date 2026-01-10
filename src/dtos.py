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


class SwapRate(Dto):
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
    type: Literal["SwapRate"] = "SwapRate"


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
    boundary_tenor: str
    libor_rate: LiborConventions
    swap_rate: SwapRateConventions


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
    t_ref: date
    market: dict[str, CcyMarket]
    static: Static
    currency: str
    tenor: str
    expiry: str


class VolSamplingParams(Dto):
    t_ref: date
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


if __name__ == "__main__":

    def run():
        params = ArbitrageParams(
            t_ref=date.fromisoformat("2025-10-12"),
            currency="USD",
            market={
                "USD": CcyMarket(
                    rates={
                        "LIBOR_RATE": Libor(
                            currency="USD",
                            tenor="3M",
                            spot_lag=2,
                            day_counter=DayCounter.ACT360,
                            calendar="NO_HOLIDAYS",
                            reset_curve=Curve(currency="USD", name="SINGLE_CURVE"),
                            bd_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
                        )
                    },
                    curves={"SINGLE_CURVE": ContinuousCompounding(rate=0.02)},
                    fixings={},
                    volatility=VolatilityCube(
                        unit=VolUnit.BpPerYear,
                        cube={
                            "3M": VolatilitySurface(
                                surface={
                                    "1Y": VolatilitySkew(
                                        skew=[
                                            (-0.0200, 100.0),
                                            (-0.0100, 80.0),
                                            (-0.0050, 72.0),
                                            (-0.0025, 70.0),
                                            (0.0000, 69.0),
                                            (0.0025, 71.0),
                                            (0.0050, 74.0),
                                            (0.0100, 90.0),
                                            (0.0200, 93.0),
                                        ]
                                    )
                                }
                            )
                        },
                    ),
                    vol_conventions=VolatilityMarketConventions(
                        boundary_tenor="10Y",
                        libor_rate=LiborConventions(
                            currency="USD",
                            spot_lag=2,
                            day_counter=DayCounter.ACT360,
                            calendar="NO_HOLIDAYS",
                            reset_curve=Curve(currency="USD", name="SINGLE_CURVE"),
                            bd_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
                        ),
                        swap_rate=SwapRateConventions(
                            spot_lag=2,
                            payment_delay=0,
                            fixed_period="3M",
                            floating_rate="LIBOR_RATE",
                            fixed_day_counter=DayCounter.ACT360,
                            calendar="NO_HOLIDAYS",
                            bd_convention=BusinessDayConvention.MODIFIED_FOLLOWING,
                            stub=StubConvention.SHORT,
                            direction=Direction.BACKWARD,
                            discount_curve=Curve(currency="USD", name="SINGLE_CURVE"),
                        ),
                    ),
                )
            },
            static=Static(calendars={"NO_HOLIDAYS": Calendar(holidays=[])}),
            expiry="10Y",
            tenor="3M",
        )

        print(ArbitrageParams.model_dump_json(params, by_alias=True))
        print("\n")
        print(
            ArbitrageCheck.model_dump_json(
                ArbitrageCheck(arbitrage=LeftAsymptotic()), by_alias=True
            )
        )
        print("\n")
        print(
            ArbitrageCheck.model_dump_json(
                ArbitrageCheck(arbitrage=Density(between=(2.0, 3.0))),
                by_alias=True,
            )
        )
        print("\n")
        print(
            ArbitrageCheck.model_validate_json(
                ArbitrageCheck.model_dump_json(
                    ArbitrageCheck(arbitrage=LeftAsymptotic()), by_alias=True
                )
            )
        )

    run()

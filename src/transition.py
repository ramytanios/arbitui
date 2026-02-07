from dataclasses import dataclass
from itertools import zip_longest
from typing import Callable, List, Optional, overload


@dataclass
class Point:
    x: float
    y: float


# transition


@overload
def transition(source: float, target: float, t: float) -> float: ...


@overload
def transition(source: Point, target: Point, t: float) -> Point: ...


@overload
def transition(source: List[Point], target: List[Point], t: float) -> List[Point]: ...


def transition(source, target, t):
    match (source, target):
        case (float(x), float(y)):
            return (1 - t) * x + t * y
        case (Point(x1, y1), Point(x2, y2)):
            return Point(
                (1 - t) * x1 + t * x2,
                (1 - t) * y1 + t * y2,
            )
        case (list() as la, list() as lb):
            res: List[Optional[Point]] = []
            for sp, tp in list(zip_longest(la, lb, fillvalue=None)):
                if sp is not None and tp is not None:
                    res.append(transition(sp, tp, t))
                elif sp is not None and tp is None:
                    res.append(None)
                else:
                    res.append(tp)
            return [p for p in res if p is not None]


# easing functions


def ease_in_cubic(t: float) -> float:
    return t * t * t


def ease_in_out_cubic(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


def ease_out_bounce(t: float) -> float:
    t = max(0.0, min(1.0, t))  # clamp

    n1 = 7.5625
    d1 = 2.75

    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


def ease_in_out_bounce(t: float) -> float:
    return (
        (1 - ease_out_bounce(1 - 2 * t)) / 2
        if t < 0.5
        else (1 + ease_out_bounce(2 * t - 1)) / 2
    )


# TODO  add more


def get_easing_func(name: str) -> Callable[[float], float]:
    match name:
        case "in_cubic":
            return ease_in_cubic
        case "in_out_cubic":
            return ease_in_out_cubic
        case "out_bounce":
            return ease_out_bounce
        case "in_out_bounce":
            return ease_in_out_bounce
        case _:
            raise Exception(f"wrong easing function {name}")

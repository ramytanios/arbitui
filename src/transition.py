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


def cubic_in(t: float) -> float:
    return t * t * t


def cubic_in_out(t: float) -> float:
    return 4 * t * t * t if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


# TODO  add more


def get_easing_func(name: str) -> Callable[[float], float]:
    match name:
        case "cubic_in":
            return cubic_in
        case "cubic_in_out":
            return cubic_in_out
        case _:
            raise Exception(f"wrong easing function {name}")

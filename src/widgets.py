from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from anyio._core._fileio import Path
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select
from textual.widgets._select import SelectOverlay
from textual.widgets._static import Static
from textual_autocomplete import PathAutoComplete
from textual_plotext.plotext_plot import PlotextPlot

import dtos
from dtos import Period
from settings import settings
from transition import Point, get_easing_func, transition


class _Suggester(Suggester):
    async def get_suggestion(self, value: str) -> str | None:
        try:
            return str(await anext(Path().glob(f"{value}*")))
        except Exception:
            return None


class _Input(Input):
    def on_mount(self) -> None:
        self.cursor_blink = True
        self.compact = True
        self.suggester = _Suggester()


class FileInput(_Input):
    @dataclass
    class FileChanged(Message):
        path: str

    @on(Input.Submitted)
    def on_submit(self, event: Input.Submitted) -> None:
        self.post_message(self.FileChanged(event.value))


class _Button(Button, can_focus=False):
    pass


class RateSelect(Select, can_focus=True, inherit_bindings=False):
    BINDINGS = [
        Binding("enter,space,l", "show_overlay", "Show Overlay", show=True),
        Binding("up,k", "cursor_up", "Cursor Up", show=True),
        Binding("down,j", "cursor_down", "Cursor Down", show=True),
    ]

    def on_mount(self) -> None:
        self.compact = True

    def action_cursor_up(self):
        if self.expanded:
            self.select_overlay.action_cursor_up()
        else:
            self.screen.focus_previous()

    def action_cursor_down(self):
        if self.expanded:
            self.select_overlay.action_cursor_down()
        else:
            self.screen.focus_next()

    @property
    def select_overlay(self) -> SelectOverlay:
        return self.query_one(SelectOverlay)


class FileBar(Widget):
    def on_mount(self) -> None:
        input = self.query_one("#file-input", FileInput)
        self.path_autocomplete = PathAutoComplete(target=input)
        self.screen.mount(self.path_autocomplete)

    version = "v0.0.1"

    def compose(self) -> ComposeResult:
        yield Label(
            f"[$primary][b]Arbitui [dim]{self.version}[/][/][/]", id="app-title"
        )
        yield FileInput(placeholder="Enter filename", id="file-input")


class QuotesPlot(PlotextPlot, can_focus=True):
    @dataclass
    class State:
        quotes: List[Point]
        interp: List[Point]
        forward: float
        tenor: dtos.Period
        expiry: dtos.Period
        arbitrage: Optional[dtos.Arbitrage]

    def __init__(self, draw_hline_zero: bool = False, *args, **kwargs):
        self.draw_hline_zero = draw_hline_zero
        super().__init__(*args, **kwargs)

    DEFAULT_CLASSES = "box"

    state: reactive[Optional[State]] = reactive(None)

    prev_curr_state: Tuple[Optional[State], Optional[State]] = (None, None)

    def transition_state(self, source: State, target: State, t: float) -> State:
        return self.State(
            transition(source.quotes, target.quotes, t),
            transition(source.interp, target.interp, t),
            transition(source.forward, target.forward, t),
            target.tenor,
            target.expiry,
            target.arbitrage,
        )

    def _format_strike(self, k: float) -> str:
        return f"{k * 100:.2f}"

    def on_mount(self) -> None:
        self.plt.xlabel("%K")

    def _draw_forward(self, fwd: float) -> None:
        self.plt.vline(fwd, "gray")

    def _draw_series(self, state: State) -> None:
        self.plt.clear_data()
        self.plt.plot(
            [p.x for p in state.interp],
            [p.y for p in state.interp],
            marker="braille",
        )
        self.plt.scatter(
            [p.x for p in state.quotes],
            [p.y for p in state.quotes],
            marker="o",
        )
        self.refresh()

    def _draw_axis(self, state: State) -> None:
        xticks = [p.x for p in state.quotes]
        xlabels = list(map(self._format_strike, xticks))
        self.plt.xticks(xticks, xlabels)
        self._draw_forward(state.forward)
        if self.draw_hline_zero:
            self.plt.hline(1e-8, "orange")
        rate_underlying = f"Θ={state.tenor},T={state.expiry}"
        match state.arbitrage:
            case None:
                self.plt.title(f"{rate_underlying}: no arbitrage found")
            case dtos.LeftAsymptotic():
                self.plt.title(f"{rate_underlying}: left asymptotic arbitrage found")
            case dtos.RightAsymptotic():
                self.plt.title(f"{rate_underlying}: right asymptotic arbitrage found")
            case dtos.Density(between=(left_strike, right_strike)):
                self.plt.title(
                    f"{rate_underlying}: density arbitrage found in ({self._format_strike(left_strike)}, {self._format_strike(right_strike)})"
                )
                self.plt.vline(left_strike, "red")
                self.plt.vline(right_strike, "red")

    async def watch_state(self, new_state: Optional[State]) -> None:
        if new_state:
            (_, curr) = self.prev_curr_state
            self.prev_curr_state = (curr, new_state)

            # if no previous state, render immediately
            if curr is None:
                self._draw_series(new_state)
                self._draw_axis(new_state)
                return

            E = get_easing_func(settings.plot_easing_function)

            start = time.perf_counter()
            frame_dt = 1 / 30
            while True:
                elapsed = time.perf_counter() - start
                u0 = elapsed / settings.plot_transition_duration_seconds
                u = E(min(max(0.0, u0), 1.0))
                intermediate_state = self.transition_state(curr, new_state, u)
                self._draw_series(intermediate_state)
                if u0 > 1.0:
                    break
                await asyncio.sleep(frame_dt)

            self._draw_axis(new_state)


class EmptyCell(Static):
    pass


class PeriodCell(Widget):
    def __init__(self, period: Period, *args, **kwargs):
        self.period = period
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Label(
            f"{self.period.length}{self.period.unit.value}", classes="period-cell"
        )


class ArbitrageCell(Static):
    __match_args__ = ("tenor", "expiry")

    def __init__(
        self,
        tenor: Period,
        expiry: Period,
        *args,
        **kwargs,
    ):
        self.tenor = tenor
        self.expiry = expiry
        super().__init__(*args, **kwargs)

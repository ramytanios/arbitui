from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from anyio._core._fileio import Path
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select
from textual.widgets._select import SelectOverlay
from textual_autocomplete import PathAutoComplete
from textual_plotext.plotext_plot import PlotextPlot

import dtos
from dtos import Period


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


@dataclass
class Quotes:
    quoted_strikes: List[float]
    quoted_vals: List[float]
    strikes: List[float]
    vals: List[float]
    fwd: float


class QuotesPlot(PlotextPlot, can_focus=True):
    def __init__(self, hline: Optional[float] = None, *args, **kwargs):
        self.hline = hline
        super().__init__(*args, **kwargs)

    DEFAULT_CLASSES = "box"

    quotes: reactive[Optional[Quotes]] = reactive(None)

    def on_mount(self) -> None:
        self.plt.xlabel("%K")

    def draw_forward(self, fwd: float) -> None:
        self.plt.vline(fwd, "gray")

    def _replot(self, new_quotes: Quotes) -> None:
        self.plt.clear_data()
        self.plt.plot(new_quotes.strikes, new_quotes.vals, marker="braille")
        self.plt.scatter(new_quotes.quoted_strikes, new_quotes.quoted_vals, marker="o")
        xticks = new_quotes.quoted_strikes
        xlabels = list(map(lambda x: f"{x * 100:.2f}", xticks))
        self.plt.xticks(xticks, xlabels)
        self.draw_forward(new_quotes.fwd)
        if x := self.hline:
            self.plt.hline(x, "red")
        self.refresh()

    def watch_quotes(self, new_quotes: Optional[Quotes]) -> None:
        if new_quotes:
            self._replot(new_quotes)


class EmptyCell(Label):
    pass


class PeriodCell(Widget):
    def __init__(self, period: Period, *args, **kwargs):
        self.period = period
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Label(
            f"{self.period.length}{self.period.unit.value}", classes="period-cell"
        )


class ArbitrageCell(Widget, can_focus=True):
    def __init__(
        self,
        tenor: Period,
        expiry: Period,
        arbitrage: dtos.ArbitrageCheck,
        *args,
        **kwargs,
    ):
        self.tenor = tenor
        self.expiry = expiry
        self.arbitrage = arbitrage
        super().__init__(*args, **kwargs)

    @dataclass
    class RateUnderlyingEntered(Message):
        tenor: Period
        expiry: Period

    def on_key(self, event: Key) -> None:
        if event.key == "enter":
            self.post_message(self.RateUnderlyingEntered(self.tenor, self.expiry))

    def compose(self) -> ComposeResult:
        match self.arbitrage.arbitrage:
            case None:
                yield Label(variant="success", classes="arbitrage-cell")
            case _:
                yield Label(variant="error", classes="arbitrage-cell")

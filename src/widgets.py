from __future__ import annotations

from dataclasses import dataclass

from anyio._core._fileio import Path
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select
from textual.widgets._select import SelectOverlay
from textual_autocomplete import PathAutoComplete
from textual_plotext.plotext_plot import PlotextPlot


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
    DEFAULT_CLASSES = "box"

    def on_mount(self) -> None:
        self.plt.xlabel("K")

    def draw_forward(self, fwd: float) -> None:
        self.plt.vline(fwd, "gray")

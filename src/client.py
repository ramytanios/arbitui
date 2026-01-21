import asyncio
from asyncio import Queue
from asyncio.queues import QueueFull
from dataclasses import dataclass, replace
from typing import Callable, Optional

import websockets
from pydantic import ValidationError
from rich.text import Text
from textual import log
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Header
from textual.widgets._data_table import DataTable
from textual.widgets._static import Static
from textual_plotext import PlotextPlot

from message import (
    ClientMsg,
    Conventions,
    FullArbitrageCheck,
    LoadCube,
    Notification,
    Ping,
    Pong,
    Rates,
    ServerMsg,
    Severity,
    VolaCube,
    VolSamples,
    client_msg_adapter,
    server_msg_adapter,
)
from widgets import ASelect, FileBar, FileInput


async def ws_async(q_in: Queue[ServerMsg], q_out: Queue[ClientMsg]) -> None:
    async with websockets.connect("ws://localhost:8000/ws") as ws:

        async def send_heartbeat():
            while True:
                try:
                    await q_out.put(Ping())
                    await asyncio.sleep(3)
                except Exception as e:
                    e.add_note(f"sending heartbeat failed: {e}")
                    raise

        async def send_loop():
            while True:
                try:
                    msg = await q_out.get()
                    await ws.send(client_msg_adapter.dump_json(msg), text=True)
                    log.info(f"sent ws message: {msg}")
                except Exception as e:
                    e.add_note(f"send loop failed: {e}")
                    raise

        async def recv_loop():
            while True:
                try:
                    msg = await ws.recv()
                    await q_in.put(server_msg_adapter.validate_json(msg))
                except ValidationError as e:
                    log.warning(f"failed to decode server message: {e}")
                except Exception as e:
                    e.add_note(f"recv loop failed: {e}")
                    raise

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_heartbeat())
                tg.create_task(send_loop())
                tg.create_task(recv_loop())
        except* Exception as e:
            log.error(f"WS connection failed in task group: ${e.exceptions}")


@dataclass
class State:
    cube: Optional[VolaCube] = None
    rates: Optional[Rates] = None
    conventions: Optional[Conventions] = None
    matrix: Optional[FullArbitrageCheck] = None
    samples: Optional[VolSamples] = None


class RatesConventions(Widget, can_focus=True):
    DEFAULT_CLASSES = "box conventions-grid"
    BORDER_TITLE = "Rates & Conventions"

    rates: reactive[Optional[Rates]] = reactive(None, recompose=True)

    conventions: reactive[Optional[Conventions]] = reactive(None, recompose=True)

    def populate_libor_table(self):
        if self.conventions:
            libor_table = self.query_one("#libor", DataTable)
            libor = self.conventions.conventions.libor[1]
            libor_table.add_columns("data", "value")
            dikt = libor.model_dump(mode="json")
            dikt["reset_curve"] = dikt["reset_curve"]["name"]
            for row in dikt.items():
                styled_row = (Text(str(row[0]), style="italic"), row[1])
                libor_table.add_row(*styled_row)

    def populate_swap_table(self):
        if self.conventions:
            swap_table = self.query_one("#swap", DataTable)
            swap = self.conventions.conventions.swap[1]
            swap_table.add_columns("data", "value")
            dikt = swap.model_dump(mode="json")
            dikt["discount_curve"] = dikt["discount_curve"]["name"]
            for row in dikt.items():
                styled_row = (Text(str(row[0]), style="italic"), row[1])
                swap_table.add_row(*styled_row)

    def compose(self) -> ComposeResult:
        if self.rates is not None and self.conventions is not None:
            yield ASelect(
                options=[(k, k) for k in self.rates.libor_rates.keys()],
                value=self.conventions.conventions.libor[0],
            )
            yield ASelect(
                options=[(k, k) for k in self.rates.swap_rates.keys()],
                value=self.conventions.conventions.swap[0],
            )
            yield DataTable(id="libor", show_header=False)
            yield DataTable(id="swap", show_header=False)

        self.call_later(self.populate_libor_table)
        self.call_later(self.populate_swap_table)


class VolaSkewChart(Widget, can_focus=True):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Volatility Smile"

    samples: reactive[Optional[VolSamples]] = reactive(None)

    def compose(self) -> ComposeResult:
        yield PlotextPlot()

    def watch_samples(self, samples: Optional[VolSamples]) -> None:
        if samples:
            plt = self.query_one(PlotextPlot).plt
            plt.cld()
            ks = samples.samples.strikes
            pdf = samples.samples.pdf
            qks = samples.samples.quoted_strikes
            qpdf = samples.samples.quoted_vols
            plt.plot(ks, pdf, color="yellow")
            plt.scatter(qks, qpdf, marker="o", color="orange")


class ArbitrageMatrix(Widget, can_focus=True):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Arbitrage Matrix"

    matrix: reactive[Optional[FullArbitrageCheck]] = reactive(None)

    def compose(self) -> ComposeResult:
        yield Static("TODO")


class DensityChart(Widget, can_focus=True):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Implied Probability Density"

    samples: reactive[Optional[VolSamples]] = reactive(None)

    def compose(self) -> ComposeResult:
        yield PlotextPlot()

    def watch_samples(self, samples: Optional[VolSamples]) -> None:
        if samples:
            plt = self.query_one(PlotextPlot).plt
            plt.cld()
            ks = samples.samples.strikes
            pdf = samples.samples.pdf
            qks = samples.samples.quoted_strikes
            qpdf = samples.samples.quoted_pdf
            plt.plot(ks, pdf, color="yellow")
            plt.scatter(qks, qpdf, marker="o", color="orange")


class Body(Widget):
    state: reactive[Optional[State]] = reactive(None)

    def compose(self) -> ComposeResult:
        yield FileBar()
        yield RatesConventions()
        yield VolaSkewChart()
        yield ArbitrageMatrix()
        yield DensityChart()

    def watch_state(self, state: State) -> None:
        if not state:
            return

        self.query_one(RatesConventions).rates = state.rates
        self.query_one(RatesConventions).conventions = state.conventions
        self.query_one(VolaSkewChart).samples = state.samples
        self.query_one(ArbitrageMatrix).matrix = state.matrix
        self.query_one(DensityChart).samples = state.samples


class Arbitui(App):
    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("n", "add_node", "Add node"),
        ("t", "add_task", "Add task"),
        ("q", "quit", "Quit"),
    ]
    CSS_PATH = "styles.tcss"

    THEME_LIGHT = "catppuccin-latte"
    THEME_DARK = "catppuccin-mocha"

    TITLE = "Arbitui"
    SUB_TITLE = "IR Volatility Manager"

    q_in = Queue[ServerMsg]()
    q_out = Queue[ClientMsg]()
    q_state_updates = Queue[Callable[[State], State]]()

    state: reactive[State] = reactive(State())

    def update_state(self, fn: Callable[[State], State]):
        try:
            self.q_state_updates.put_nowait(fn)
        except QueueFull as e:
            log.error(f"state update Q is full: {e}")

    async def on_mount(self) -> None:
        self.theme = self.THEME_DARK
        self.run_worker(ws_async(self.q_in, self.q_out))
        self.run_worker(self.recv_loop())
        self.run_worker(self.state_updates_loop())

    async def recv_loop(self):
        while True:
            try:
                msg = await self.q_in.get()
                await self.handle_server_msg(msg)
            except Exception:
                log.error("exception in receive loop: {e}")

    async def handle_server_msg(self, msg: ServerMsg):
        match msg:
            case Pong():
                log.info("pong received")
            case Rates() as rates:
                log.info("updating rates state")
                self.update_state(lambda s: replace(s, rates=rates))
            case Conventions() as conventions:
                log.info("updating conventions state")
                self.update_state(lambda s: replace(s, conventions=conventions))
            case FullArbitrageCheck() as matrix:
                log.info("updating arbitrage matrix state")
                self.update_state(lambda s: replace(s, matrix=matrix))
            case VolSamples() as samples:
                log.info("updating vol samples state")
                self.update_state(lambda s: replace(s, samples=samples))
            case VolaCube() as cube:
                log.info(f"received vol cube currency {cube.currency}")
                self.update_state(lambda s: replace(s, cube=cube))
            case Notification(msg=msg, severity=severity):
                s = None
                match severity:
                    case Severity.ERROR:
                        s = "error"
                    case Severity.WARNING:
                        s = "warning"
                    case Severity.INFORMATION:
                        s = "information"
                if s:
                    self.notify(message=msg, severity=s)

    async def state_updates_loop(self):
        while True:
            try:
                fn = await self.q_state_updates.get()
                self.state = fn(self.state)
            except Exception as e:
                log.error(f"state update failed: {e}")

    def action_toggle_dark(self) -> None:
        self.theme = (
            self.THEME_LIGHT if self.theme == self.THEME_DARK else self.THEME_DARK
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Body().data_bind(Arbitui.state)
        yield Footer()

    async def on_file_input_filename(self, event: FileInput.Filename) -> None:
        try:
            await self.q_out.put(LoadCube(file_path=event.path))
        except Exception as e:
            self.notify(message=f"failed to handle fileinput event {e}")


if __name__ == "__main__":
    app = Arbitui()
    app.run()

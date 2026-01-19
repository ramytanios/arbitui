import asyncio
from asyncio import Queue
from asyncio.queues import QueueFull
from dataclasses import dataclass, replace
from typing import Callable, Optional

import websockets
from pydantic import ValidationError
from textual import log
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Header, Input
from textual.widgets._button import Button
from textual.widgets._select import Select
from textual.widgets._static import Static
from textual_plotext import PlotextPlot

from message import (
    ClientMsg,
    Conventions,
    FullArbitrageCheck,
    Ping,
    Pong,
    Rates,
    ServerMsg,
    VolSamples,
    client_msg_adapter,
    server_msg_adapter,
)


async def ws_async(q_in: Queue[ServerMsg], q_out: Queue[ClientMsg]) -> None:
    async with websockets.connect("ws://127.0.0.1:8090/api/ws") as ws:

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
                    await ws.send(client_msg_adapter.dump_json(msg))
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
    rates: Optional[Rates] = None
    conventions: Optional[Conventions] = None
    matrix: Optional[FullArbitrageCheck] = None
    samples: Optional[VolSamples] = None

    def modify(
        self,
        rates: Optional[Rates] = None,
        conventions: Optional[Conventions] = None,
        matrix: Optional[FullArbitrageCheck] = None,
        samples: Optional[VolSamples] = None,
    ):
        return replace(
            self,
            rates=rates,
            conventions=conventions,
            matrix=matrix,
            samples=samples,
        )


class RatesConventions(Widget, can_focus=True):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Rates & Conventions"

    rates: reactive[Optional[Rates]] = reactive(None)

    conventions: reactive[Optional[Conventions]] = reactive(None)

    def compose(self) -> ComposeResult:
        if self.rates is not None and self.conventions is not None:
            saved_libor = self.rates.libor_rates.get(
                self.conventions.conventions.libor[0],
            )
            saved_swap = self.rates.swap_rates.get(
                self.conventions.conventions.swap[0],
            )
            if saved_libor is not None and saved_swap is not None:
                yield Select(
                    list(self.rates.libor_rates.items()),
                    value=saved_libor,
                    allow_blank=False,
                    compact=True,
                )
                yield Select(
                    list(self.rates.swap_rates.items()),
                    value=saved_swap,
                    allow_blank=False,
                    compact=True,
                )


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


class FileInput(Input):
    def on_mount(self) -> None:
        self.cursor_blink = True
        self.compact = True


class FileLoadButton(Button, can_focus=False):
    pass


class FileBar(Widget):
    def compose(self) -> ComposeResult:
        yield FileInput(placeholder="Enter filename", id="file-input")
        yield FileLoadButton(label="Load", compact=True, id="file-load")


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
        self.run_worker(ws_async(self.q_in, self.q_out), exit_on_error=False)
        self.run_worker(self.recv_loop(), exit_on_error=False)
        self.run_worker(self.state_updates_loop(), exit_on_error=False)

    async def recv_loop(self):
        while True:
            try:
                msg = await self.q_in.get()
                self.handle_server_msg(msg)
            except Exception:
                log.error("exception in receive loop: {e}")

    def handle_server_msg(self, msg: ServerMsg):
        match msg:
            case Pong():
                log.info("pong received")
            case Rates() as rates:
                log.info("updating rates state")
                self.update_state(lambda s: s.modify(rates=rates))
            case Conventions() as conventions:
                log.info("updating conventions state")
                self.update_state(lambda s: s.modify(conventions=conventions))
            case FullArbitrageCheck() as matrix:
                log.info("updating arbitrage matrix state")
                self.update_state(lambda s: s.modify(matrix=matrix))
            case VolSamples() as samples:
                log.info("updating vol samples state")
                self.update_state(lambda s: s.modify(samples=samples))

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


if __name__ == "__main__":
    app = Arbitui()
    app.run()

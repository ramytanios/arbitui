import asyncio
from asyncio import Queue
from dataclasses import dataclass, replace
from typing import Callable, Optional

import websockets
from pydantic import ValidationError
from textual import log
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Header
from textual.widgets._static import Static
from textual_plotext import PlotextPlot

from message import (
    ClientMsg,
    Conventions,
    FullArbitrageCheck,
    Ping,
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


class RatesConventions(Widget):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Rates & Conventions"

    def compose(self) -> ComposeResult:
        yield Static("TODO")


class VolaSkewChart(Widget):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Volatility Smile"

    def compose(self) -> ComposeResult:
        yield PlotextPlot()

    def on_mount(self) -> None:
        plt = self.query_one(PlotextPlot).plt
        y = plt.sin()
        plt.scatter(y)


class ArbitrageMatrix(Widget):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Arbitrage Matrix"

    def compose(self) -> ComposeResult:
        yield Static("TODO")


class DensityChart(Widget):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Implied Probability Density"

    def compose(self) -> ComposeResult:
        yield PlotextPlot()

    def on_mount(self) -> None:
        plt = self.query_one(PlotextPlot).plt
        y = plt.sin()
        plt.scatter(y)


class Body(Widget):
    def compose(self) -> ComposeResult:
        yield RatesConventions()
        yield VolaSkewChart()
        yield ArbitrageMatrix()
        yield DensityChart()


@dataclass
class State:
    rates: Optional[Rates] = None
    conventions: Optional[Conventions] = None
    matrix: Optional[FullArbitrageCheck] = None
    samples: Optional[VolSamples] = None

    def with_rates(self, v: Rates):
        return replace(self, rates=v)

    def with_conventions(self, v: Rates):
        return replace(self, conventions=v)

    def with_matrix(self, v: FullArbitrageCheck):
        return replace(self, matrix=v)

    def with_samples(self, v: VolSamples):
        return replace(self, samples=v)


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

    state: reactive[State] = reactive(State())

    def update_state(self, f: Callable[[State], State]):
        self.state = f(self.state)

    async def on_mount(self) -> None:
        self.theme = self.THEME_DARK
        self.run_worker(ws_async(self.q_in, self.q_out), exit_on_error=False)

    def action_toggle_dark(self) -> None:
        self.theme = (
            self.THEME_LIGHT if self.theme == self.THEME_DARK else self.THEME_DARK
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Body()
        yield Footer()


if __name__ == "__main__":
    app = Arbitui()
    app.run()

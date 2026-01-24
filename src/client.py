from widgets import QuotesPlot
import asyncio
from asyncio import Queue
from asyncio.queues import QueueFull
from dataclasses import dataclass, replace
from typing import Callable, Optional

import websockets
from pydantic import ValidationError
from rich.text import Text
from textual import log, on
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Header, Label, Select
from textual_plotext import PlotextPlot

from message import (
    ArbitrageMatrix,
    ClientMsg,
    Conventions,
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
from theme import rates_terminal_theme
from widgets import FileBar, FileInput, RateSelect


async def ws_async(q_in: Queue[ServerMsg], q_out: Queue[ClientMsg]) -> None:
    async with websockets.connect("ws://localhost:8000/ws") as ws:

        async def send_heartbeat():
            while True:
                try:
                    await q_out.put(Ping())
                    await asyncio.sleep(3)
                except Exception as e:
                    log.error(f"sending heartbeat failed: {e}")

        async def send_loop():
            while True:
                try:
                    msg = await q_out.get()
                    await ws.send(client_msg_adapter.dump_json(msg), text=True)
                    log.info(f"sent ws message: {msg}")
                except Exception as e:
                    log.error(f"send loop failed: {e}")

        async def recv_loop():
            while True:
                try:
                    msg = await ws.recv()
                    await q_in.put(server_msg_adapter.validate_json(msg))
                except ValidationError as e:
                    log.error(f"failed to decode server message: {e}")
                except Exception as e:
                    log.error(f"recv loop failed: {e}")

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
    matrix: Optional[ArbitrageMatrix] = None
    samples: Optional[VolSamples] = None


class RatesConventions(Widget, can_focus=True):
    DEFAULT_CLASSES = "box conventions-grid"
    BORDER_TITLE = "Rates & Conventions"

    rates: reactive[Optional[Rates]] = reactive(None, recompose=True)
    conventions: reactive[Optional[Conventions]] = reactive(None, recompose=True)
    selected_libor: reactive[Optional[str]] = reactive(None)
    selected_swap: reactive[Optional[str]] = reactive(None)

    def fill_libor_table(self):
        if self.rates is not None and self.selected_libor is not None:
            libor = self.rates.libor_rates.get(self.selected_libor)
            if libor is not None:
                libor_table = self.query_one("#libor-table", DataTable)
                libor_table.clear()
                libor_table.add_columns("data", "value")
                dikt = libor.to_conventions().model_dump(mode="json")
                dikt["reset_curve"] = dikt["reset_curve"]["name"]
                for row in dikt.items():
                    styled_row = (Text(str(row[0]), style="italic"), row[1])
                    libor_table.add_row(*styled_row)

    def fill_swap_table(self):
        if self.rates is not None and self.selected_swap is not None:
            swap = self.rates.swap_rates.get(self.selected_swap)
            if swap is not None:
                swap_table = self.query_one("#swap-table", DataTable)
                swap_table.clear()
                swap_table.add_columns("data", "value")
                dikt = swap.to_conventions().model_dump(mode="json")
                dikt["discount_curve"] = dikt["discount_curve"]["name"]
                for row in dikt.items():
                    styled_row = (Text(str(row[0]), style="italic"), row[1])
                    swap_table.add_row(*styled_row)

    def watch_selected_libor(self) -> None:
        self.fill_libor_table()

    def watch_selected_swap(self) -> None:
        self.fill_swap_table()

    def compose(self) -> ComposeResult:
        if self.rates is not None and self.conventions is not None:
            yield RateSelect(
                options=[(k, k) for k in self.rates.libor_rates.keys()],
                id="libor-select",
                allow_blank=False,
            )
            yield RateSelect(
                options=[(k, k) for k in self.rates.swap_rates.keys()],
                id="swap-select",
                allow_blank=False,
            )
            yield DataTable(id="libor-table", show_header=False)
            yield DataTable(id="swap-table", show_header=False)
            cvs = self.conventions.conventions
            yield Label(
                f"[b $primary]●[dim] Libor Convention:[/] {cvs.libor_rate[0]}[/]"
            )
            yield Label(
                f"[b $primary]●[dim] Swap Convention:[/] {cvs.swap_rate[0]}[/]",
            )
        # self.call_later(self.populate_tables)

    @on(Select.Changed, "#libor-select")
    def libor_selected(self, event: Select.Changed) -> None:
        self.log.debug(f"libor selected {event.value}")
        self.selected_libor = str(event.value)

    @on(Select.Changed, "#swap-select")
    def swap_selected(self, event: Select.Changed) -> None:
        self.log.debug(f"swap selected {event.value}")
        self.selected_swap = str(event.value)


class ArbitrageGrid(Widget, can_focus=True):
    DEFAULT_CLASSES = "box"
    BORDER_TITLE = "Arbitrage Matrix"

    matrix: reactive[Optional[ArbitrageMatrix]] = reactive(None, recompose=True)

    def compose(self) -> ComposeResult:
        yield Label("TODO")


class VolaSkewChart(QuotesPlot, can_focus=True):
    BORDER_TITLE = "Volatility Smile"

    samples: reactive[Optional[VolSamples]] = reactive(None)

    def _replot(self, samples: VolSamples) -> None:
        self.plt.clear_data()
        data = samples.samples
        self.plt.plot(data.strikes, data.vols, marker="braille")
        self.plt.scatter(data.quoted_strikes, data.quoted_vols, marker="o")
        self.draw_forward(data.fwd)
        self.refresh()

    def watch_samples(self, samples: Optional[VolSamples]) -> None:
        if samples:
            self._replot(samples)


class DensityChart(QuotesPlot, can_focus=True):
    BORDER_TITLE = "Implied Probability Density"

    samples: reactive[Optional[VolSamples]] = reactive(None)

    def replot(self, samples: VolSamples) -> None:
        self.plt.clear_data()
        data = samples.samples
        self.plt.plot(data.strikes, data.pdf, marker="braille")
        self.plt.scatter(data.quoted_strikes, data.quoted_pdf, marker="o")
        self.plt.hline(0.0, "orange")
        self.draw_forward(data.fwd)
        self.refresh()

    def watch_samples(self, samples: Optional[VolSamples]) -> None:
        if samples:
            self.replot(samples)


class Body(Widget):
    state: reactive[Optional[State]] = reactive(None)

    def compose(self) -> ComposeResult:
        yield FileBar()
        yield RatesConventions()
        yield VolaSkewChart()
        yield ArbitrageGrid()
        yield DensityChart()

    def watch_state(self, state: State) -> None:
        if not state:
            return

        self.query_one(RatesConventions).rates = state.rates
        self.query_one(RatesConventions).conventions = state.conventions
        self.query_one(VolaSkewChart).samples = state.samples
        self.query_one(DensityChart).samples = state.samples
        self.query_one(ArbitrageGrid).matrix = state.matrix


class Arbitui(App):
    CSS_PATH = "styles.tcss"

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
        self.run_worker(ws_async(self.q_in, self.q_out))
        self.run_worker(self.recv_loop())
        self.run_worker(self.state_updates_loop())
        self.register_theme(rates_terminal_theme)
        self.theme = "rates-terminal"

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
            case ArbitrageMatrix() as matrix:
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Body().data_bind(Arbitui.state)
        yield Footer()

    async def on_file_input_file_changed(self, event: FileInput.FileChanged) -> None:
        try:
            await self.q_out.put(LoadCube(file_path=event.path))
        except Exception as e:
            self.notify(message=f"failed to handle fileinput event {e}")


if __name__ == "__main__":
    app = Arbitui()
    app.run()

import asyncio
from asyncio import Queue
from asyncio.queues import QueueFull
from dataclasses import dataclass, replace
from typing import Callable, List, Optional, Tuple

import websockets
from pydantic import ValidationError
from rich.text import Text
from textual import log, on
from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Header, Label, Select

import dtos
from message import (
    ArbitrageMatrix,
    ClientMsg,
    Conventions,
    GetVolSamples,
    LoadCube,
    Notification,
    Ping,
    Pong,
    Rates,
    ServerMsg,
    VolaCube,
    VolSamples,
    client_msg_adapter,
    server_msg_adapter,
)
from theme import rates_terminal_theme
from widgets import (
    ArbitrageCell,
    EmptyCell,
    FileBar,
    FileInput,
    PeriodCell,
    QuotesPlot,
    RateSelect,
)


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
        if (rates := self.rates) is not None and (
            conventions := self.conventions
        ) is not None:
            yield RateSelect(
                options=[(k, k) for k in rates.libor_rates.keys()],
                id="libor-select",
                allow_blank=False,
            )
            yield RateSelect(
                options=[(k, k) for k in rates.swap_rates.keys()],
                id="swap-select",
                allow_blank=False,
            )
            yield DataTable(id="libor-table", show_header=False)
            yield DataTable(id="swap-table", show_header=False)
            cvs = conventions.conventions
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

    BINDINGS = [
        ("l", "cell_next", "cell next"),
        ("h", "cell_prev", "cell prev"),
        ("j", "cell_down", "cell down"),
        ("k", "cell_up", "cell up"),
        ("tab", "tab"),
    ]

    matrix: reactive[Optional[ArbitrageMatrix]] = reactive(None, recompose=True)
    tenors: reactive[List[dtos.Period]] = reactive([])
    expiries: reactive[List[dtos.Period]] = reactive([])
    widgets: reactive[List[Widget]] = reactive([])
    selected_pair: reactive[Optional[Tuple[dtos.Period, dtos.Period]]] = reactive(None)
    n_cols: reactive[int] = reactive(0)
    n_rows: reactive[int] = reactive(0)

    def action_tab(self) -> None:
        pass

    def action_cell_next(self) -> None:
        if curr := self.selected_pair:
            curr_ij = (self.tenors.index(curr[0]), self.expiries.index(curr[1]))
            next_ij = (min(curr_ij[0] + 1, len(self.tenors) - 1), curr_ij[1])
            next = (self.tenors[next_ij[0]], self.expiries[next_ij[1]])
            self.selected_pair = next

    def action_cell_prev(self) -> None:
        if curr := self.selected_pair:
            curr_ij = (self.tenors.index(curr[0]), self.expiries.index(curr[1]))
            prev_ij = (max(curr_ij[0] - 1, 0), curr_ij[1])
            prev = (self.tenors[prev_ij[0]], self.expiries[prev_ij[1]])
            self.selected_pair = prev

    def action_cell_down(self) -> None:
        if curr := self.selected_pair:
            curr_ij = (self.tenors.index(curr[0]), self.expiries.index(curr[1]))
            down_ij = (curr_ij[0], min(curr_ij[1] + 1, len(self.expiries) - 1))
            down = (self.tenors[down_ij[0]], self.expiries[down_ij[1]])
            self.selected_pair = down

    def action_cell_up(self) -> None:
        if curr := self.selected_pair:
            curr_ij = (self.tenors.index(curr[0]), self.expiries.index(curr[1]))
            up_ij = (curr_ij[0], max(curr_ij[1] - 1, 0))
            up = (self.tenors[up_ij[0]], self.expiries[up_ij[1]])
            self.selected_pair = up

    def compute_widgets(self) -> List[Widget]:
        by_rate = {}
        if data := self.matrix:
            by_rate = {(t, e): v for t, e, v in data.matrix}
        elems: list[Widget] = []
        elems.append(EmptyCell())
        for tenor in self.tenors:
            elems.append(PeriodCell(tenor))
        for expiry in self.expiries:
            elems.append(PeriodCell(expiry))
            for tenor in self.tenors:
                if arb := by_rate.get((tenor, expiry)):
                    elems.append(
                        ArbitrageCell(tenor, expiry, arb, id=f"T{tenor}E{expiry}")
                    )
        return elems

    def watch_selected_pair(self) -> None:
        if pair := self.selected_pair:
            for widget in self.widgets:
                match widget:
                    case ArbitrageCell(tenor=tenor, expiry=expiry) if (
                        pair[0] == tenor and pair[1] == expiry
                    ):
                        try:
                            widget_cell = self.query_one(
                                f"#T{tenor}E{expiry}", ArbitrageCell
                            )
                            self.app.set_focus(widget_cell)
                        except Exception:
                            pass

    def compute_tenors(self) -> List[dtos.Period]:
        if data := self.matrix:
            return sorted(list({t for t, *_ in data.matrix}))
        else:
            return []

    def compute_expiries(self) -> List[dtos.Period]:
        if data := self.matrix:
            return sorted(list({e for _, e, *_ in data.matrix}))
        else:
            return []

    def compute_n_cols(self) -> int:
        return len(self.tenors) + 1

    def compute_n_rows(self) -> int:
        return len(self.expiries) + 1

    def compose(self) -> ComposeResult:
        grid = Grid(*self.widgets, classes="matrix-grid")
        grid.set_styles(
            f"""
                 grid-size: {self.n_cols} {self.n_rows};
                 grid-columns: 1fr;
                 grid-rows: 1;
            """
        )
        yield grid


class VolaSkewChart(QuotesPlot):
    BORDER_TITLE = "Volatility Smile"


class DensityChart(QuotesPlot):
    BORDER_TITLE = "Implied Probability Density"


class Body(Widget):
    state: reactive[Optional[State]] = reactive(None)

    def compose(self) -> ComposeResult:
        yield FileBar()
        yield RatesConventions()
        yield VolaSkewChart()
        yield ArbitrageGrid()
        yield DensityChart(draw_hline_zero=True)

    def watch_state(self, state: State) -> None:
        if not state:
            return

        self.query_one(RatesConventions).rates = state.rates
        self.query_one(RatesConventions).conventions = state.conventions
        self.query_one(ArbitrageGrid).matrix = state.matrix

        if (data := state.samples) is not None and (matrix := state.matrix) is not None:
            samples = data.samples
            tenor = data.tenor
            expiry = data.expiry
            arbitrage = next(
                a for (t, e, a) in matrix.matrix if t == tenor and e == expiry
            )
            self.query_one(VolaSkewChart).state = VolaSkewChart.State(
                samples.quoted_strikes,
                samples.quoted_vols,
                samples.strikes,
                samples.vols,
                samples.fwd,
                tenor,
                expiry,
                arbitrage.arbitrage,
            )
            self.query_one(DensityChart).state = DensityChart.State(
                samples.quoted_strikes,
                samples.quoted_pdf,
                samples.strikes,
                samples.pdf,
                samples.fwd,
                tenor,
                expiry,
                arbitrage.arbitrage,
            )
            self.query_one(ArbitrageGrid).selected_pair = (tenor, expiry)


class Arbitui(App):
    CSS_PATH = "styles.tcss"

    TITLE = "Arbitui"
    SUB_TITLE = "IR Volatility Manager"

    BINDINGS = [
        ("a", "jump_to_matrix", "Jump to matrix"),
    ]

    q_in = Queue[ServerMsg]()
    q_out = Queue[ClientMsg]()
    q_state_updates = Queue[Callable[[State], State]]()

    state: reactive[State] = reactive(State())

    def action_jump_to_matrix(self) -> None:
        matrix = self.query_one(ArbitrageGrid)
        matrix.focus()

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
            except Exception as e:
                log.error(f"exception in receive loop: {e}")

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
                self.notify(message=msg, severity=severity.to_textual())

    async def state_updates_loop(self):
        while True:
            fn = await self.q_state_updates.get()
            try:
                self.state = fn(self.state)
            except Exception as e:
                log.error(f"state update {fn} failed: {e}")
                raise  # crash app on purpose

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Body().data_bind(Arbitui.state)
        yield Footer()

    async def on_arbitrage_cell_rate_underlying_entered(
        self, event: ArbitrageCell.RateUnderlyingEntered
    ) -> None:
        if cube := self.state.cube:
            await self.q_out.put(
                GetVolSamples(
                    currency=cube.currency,
                    vol_cube=cube.cube,
                    tenor=event.tenor,
                    expiry=event.expiry,
                )
            )

    async def on_file_input_file_changed(self, event: FileInput.FileChanged) -> None:
        try:
            await self.q_out.put(LoadCube(file_path=event.path))
        except Exception as e:
            self.notify(message=f"failed to handle fileinput event {e}")
        else:
            self.set_focus(self.query_one(RatesConventions))


if __name__ == "__main__":
    app = Arbitui()
    app.run()

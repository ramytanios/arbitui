import asyncio
from asyncio import Queue

import websockets
from pydantic import ValidationError
from textual import log
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from message import ClientMsg, Ping, ServerMsg, client_msg_adapter, server_msg_adapter


async def ws_async() -> None:
    q_in = Queue[ServerMsg]()
    q_out = Queue[ClientMsg]()

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

    async def on_mount(self) -> None:
        self.theme = self.THEME_DARK
        self.run_worker(ws_async(), exit_on_error=False)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()


if __name__ == "__main__":
    app = Arbitui()
    app.run()

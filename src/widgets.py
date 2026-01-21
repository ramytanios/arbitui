from dataclasses import dataclass

from anyio._core._fileio import Path
from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Button, Input, Select


class ASuggester(Suggester):
    async def get_suggestion(self, value: str) -> str | None:
        try:
            return str(await anext(Path().glob(f"{value}*")))
        except Exception:
            return None


class AInput(Input):
    def on_mount(self) -> None:
        self.cursor_blink = True
        self.compact = True
        self.suggester = ASuggester()


class FileInput(AInput):
    @dataclass
    class Filename(Message):
        path: str

    @on(Input.Submitted)
    def on_submit(self, event: Input.Submitted) -> None:
        self.post_message(self.Filename(event.value))


class AButton(Button, can_focus=False):
    pass


class ASelect(Select, can_focus=True):
    def on_mount(self) -> None:
        self._allow_blank = True
        self.compact = True


class FileBar(Widget):
    def compose(self) -> ComposeResult:
        yield FileInput(placeholder="Enter filename", id="file-input")
        yield AButton(label="Load", compact=True, id="file-load")

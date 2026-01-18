fmt:
    just --fmt --unstable

repl:
    PYTHONPATH=src uv run --with pydantic python

run-server:
    PYTHONPATH=src uv run uvicorn server:app

console-tui:
    PYTHONPATH=src uv run textual console

[working-directory('src')]
run-tui:
    uv run client.py

[working-directory('src')]
run-dev-tui:
    uv run textual run --dev client.py

ws-client:
    websocat ws://localhost:8000/ws

tui-gif:
    vhs tui.tape

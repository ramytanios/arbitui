repl:
	PYTHONPATH=src uv run --with pydantic python


run-server:
  PYTHONPATH=src uv run uvicorn server:app

dummy-client:
  websocat ws://localhost:8000/ws

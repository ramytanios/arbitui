from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    home: Path = Path.home() / ".local" / "share" / "arbitui"
    server_ws_url: str = "ws://localhost:8000/ws"
    rpc_url: str = "http://localhost:8090/rpc" # TODO remove
    lib_socket_path: str = "/tmp/rates-scope.sock"
    file_search_path: str = "."
    max_requests_in_flight: int = 512
    vol_sampling_cache_ttl: int = 360
    bulk_arbitrage_matrix: bool = True
    ws_heartbeat_seconds: int = 3
    plot_transition_duration_seconds: float = 0.10
    plot_easing_function: str = "in_out_cubic"

    model_config = SettingsConfigDict(env_prefix="arbitui_")


settings = Settings()

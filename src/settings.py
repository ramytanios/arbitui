from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    home: Path = Path.home() / ".local" / "share" / "arbitui"
    rpc_url: str = "http://localhost:8090/rpc"
    file_search_path: str = "."
    max_requests_in_flight: int = 512
    vol_sampling_cache_ttl: int = 360
    bulk_arbitrage_matrix: bool = True
    ws_heartbeat_seconds: int = 3

    model_config = SettingsConfigDict(env_prefix="arbitui_")


settings = Settings()

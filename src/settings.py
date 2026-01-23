from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    home: Path = Path.home() / ".local" / "share" / "arbitui"
    rpc_url: str = "http://localhost:8090/rpc"
    file_search_path: str = "."
    show_version: bool = True

    model_config = SettingsConfigDict(env_prefix="arbitui_")


settings = Settings()

from pathlib import Path
from typing import Annotated
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_token: str
    google_creds_path: str = "./secrets/google_creds.json"
    sheet_id: str
    sheet_tab_name: str = "Transaksi"
    allowed_user_ids: Annotated[set[int], NoDecode] = Field(default_factory=set)
    ollama_base_url: str = "http://localhost:11434"
    ollama_text_model: str = "qwen2.5:7b"
    ollama_vision_model: str = "llava:7b"
    log_level: str = "INFO"
    tz: str = "Asia/Jakarta"
    confidence_threshold: float = 0.8

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_ids(cls, v):
        if isinstance(v, str):
            return {int(x.strip()) for x in v.split(",") if x.strip()}
        return v

    def creds_abs_path(self) -> Path:
        p = Path(self.google_creds_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


settings = Settings()  # type: ignore[call-arg]

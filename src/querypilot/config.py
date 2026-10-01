from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QP_", env_file=".env", extra="ignore")

    model: str = "gpt-4o-mini"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "QP_OPENAI_API_KEY"),
    )
    openai_api_base: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_API_BASE", "OPENAI_BASE_URL", "QP_API_BASE"),
    )
    db_dir: Path = Path("./benchmarks/databases")
    sql_timeout_s: int = 10
    max_rows: int = 500
    max_repairs: int = 3
    max_steps: int = 15
    mock_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("QP_MOCK", "QP_MOCK_MODE"),
    )
    accuracy_tolerance: float = 2.0
    cost_per_1k_in: float = 0.00015
    cost_per_1k_out: float = 0.0006


settings = Settings()

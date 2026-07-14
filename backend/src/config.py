from __future__ import annotations

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    upload_dir: str = "uploads"
    max_upload_size: int = 25 * 1024 * 1024  # 25MB

    model_config = {"env_file": ".env"}


settings = Settings()
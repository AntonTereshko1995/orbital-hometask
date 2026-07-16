from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    upload_dir: str = "uploads"
    max_upload_size: int = 25 * 1024 * 1024  # 25MB
    agentic_search_threshold: int = 1_000
    rag_token_threshold: int = 9_000
    sub_agent_max_iterations: int = 10
    embedding_model: str = ""
    embedding_api_key: str = ""
    rag_top_k: int = 10

    model_config = {"env_file": ".env"}


settings = Settings()

from __future__ import annotations

# config must be imported before any LiteLLM calls so that its module-level code
# calls os.environ.setdefault("ANTHROPIC_API_KEY", ...) and
# os.environ.setdefault("XAI_API_KEY", ...).
# LiteLLM reads these env vars when it makes the first API call.
from config import settings  # noqa: F401  # pyright: ignore[reportUnusedImport]

MODEL: str = settings.llm_model
API_KEY: str = settings.llm_api_key

from __future__ import annotations

from ai.prompts import LEGAL_ASSISTANT_SYSTEM_PROMPT

# config must be imported before the Agent is instantiated so that its module-level code
# calls os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key).
# PydanticAI reads ANTHROPIC_API_KEY when it initializes the Anthropic backend client.
from config import settings  # noqa: F401  # pyright: ignore[reportUnusedImport]
from pydantic_ai import Agent

agent = Agent(
    "anthropic:claude-haiku-4-5-20251001",
    system_prompt=LEGAL_ASSISTANT_SYSTEM_PROMPT,
)

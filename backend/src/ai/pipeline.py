from __future__ import annotations

from collections.abc import AsyncIterator

import litellm

from ai.agent import API_KEY, MODEL
from ai.prompts import LEGAL_ASSISTANT_SYSTEM_PROMPT


async def chat_with_document(
    user_message: str,
    document_text: str | None,
    conversation_history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Stream a response to the user's message, yielding text chunks.

    Builds a prompt containing document context and conversation history,
    then streams the response from the LLM.
    """
    prompt_parts: list[str] = []

    if document_text:
        prompt_parts.append(
            "The following is the content of the document being discussed:\n\n"
            "<document>\n"
            f"{document_text}\n"
            "</document>\n"
        )
    else:
        prompt_parts.append(
            "No document has been uploaded yet. If the user asks about a document, "
            "let them know they need to upload one first.\n"
        )

    if conversation_history:
        prompt_parts.append("Previous conversation:\n")
        for msg in conversation_history:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")
        prompt_parts.append("\n")

    prompt_parts.append(f"User: {user_message}")
    full_prompt = "\n".join(prompt_parts)

    messages = [
        {"role": "system", "content": LEGAL_ASSISTANT_SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt},
    ]

    stream = await litellm.acompletion(model=MODEL, messages=messages, stream=True, api_key=API_KEY)  # type: ignore[misc]  # pyright: ignore[reportUnknownMemberType]
    async for chunk in stream:  # type: ignore[union-attr]
        content = chunk.choices[0].delta.content  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
        if content:
            yield content


async def generate_title(user_message: str) -> str:
    """Generate a 3-5 word conversation title from the first user message."""
    response = await litellm.acompletion(  # type: ignore[misc]
        model=MODEL,
        api_key=API_KEY,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Generate a concise 3-5 word title for a conversation that starts with: "
                    f"'{user_message}'. Return only the title, nothing else."
                ),
            }
        ],
    )
    raw = response.choices[0].message.content  # type: ignore[union-attr]  # pyright: ignore[reportUnknownMemberType]
    title = str(raw or "").strip().strip('"').strip("'")  # pyright: ignore[reportUnknownArgumentType]
    if len(title) > 100:
        title = title[:97] + "..."
    return title

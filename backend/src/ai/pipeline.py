from __future__ import annotations

from collections.abc import AsyncIterator

import litellm
import structlog

from ai.agent import API_KEY, MODEL
from ai.prompts import LEGAL_ASSISTANT_SYSTEM_PROMPT
from ai.sub_agent import run_document_sub_agent
from ai.types import DocContext, SectionData
from config import settings
from services.rag import retrieve_top_k_chunks

logger = structlog.get_logger()


def estimate_tokens(documents: list[DocContext]) -> int:
    """Return the total token count across all document texts. Synchronous."""
    total = 0
    for doc in documents:
        if doc["text"]:
            total += litellm.token_counter(model=MODEL, text=doc["text"])  # type: ignore[misc]
    return total


async def chat_with_document(
    user_message: str,
    documents: list[DocContext],
    conversation_history: list[dict[str, str]],
    sections_by_doc: dict[str, list[SectionData]] | None = None,
) -> AsyncIterator[str]:
    """Stream a response, choosing Level 1, 2, or 3 based on document size.

    Level 1: all document text injected directly into the prompt.
    Level 2: a sub-agent navigates documents via tools and returns findings;
             only those findings are included in the main prompt.
    Level 3: user query is embedded; only the top-K semantically similar
             chunks are injected into the main prompt.
    """
    total_tokens = estimate_tokens(documents)

    use_level3 = total_tokens > settings.rag_token_threshold and any(
        doc["embedding_path"] for doc in documents
    )
    use_level2 = (
        not use_level3
        and total_tokens > settings.level2_token_threshold
        and total_tokens < settings.rag_token_threshold
        and sections_by_doc is not None
        and bool(documents)
    )

    if use_level3:
        logger.info(
            "Routing decision",
            level=3,
            total_tokens=total_tokens,
            threshold=settings.rag_token_threshold,
        )
        async for chunk in _level3_chat(user_message, documents, conversation_history):
            yield chunk
    elif use_level2:
        logger.info(
            "Routing decision",
            level=2,
            total_tokens=total_tokens,
            threshold=settings.level2_token_threshold,
        )
        async for chunk in _level2_chat(
            user_message,
            documents,
            conversation_history,
            sections_by_doc,  # pyright: ignore[reportArgumentType]
        ):
            yield chunk
    else:
        logger.info(
            "Routing decision",
            level=1,
            total_tokens=total_tokens,
            threshold=settings.level2_token_threshold,
        )
        async for chunk in _level1_chat(user_message, documents, conversation_history):
            yield chunk


async def _level1_chat(
    user_message: str,
    documents: list[DocContext],
    conversation_history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Level 1: inject all document text into the prompt."""
    prompt_parts: list[str] = []

    if documents:
        count = len(documents)
        label = "document" if count == 1 else "documents"
        prompt_parts.append(f"You have access to {count} {label}:\n\n")
        for doc in documents:
            text = doc["text"].strip() if doc["text"].strip() else "[Content could not be extracted]"
            prompt_parts.append(f'<document name="{doc["filename"]}">\n{text}\n</document>\n\n')
    else:
        prompt_parts.append(
            "No documents have been uploaded yet. "
            "Let the user know they need to upload a document first.\n"
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


async def _level2_chat(
    user_message: str,
    documents: list[DocContext],
    conversation_history: list[dict[str, str]],
    sections_by_doc: dict[str, list[SectionData]],
) -> AsyncIterator[str]:
    """Level 2: sub-agent explores documents, findings are fed to the main LLM."""
    doc_map = {doc["id"]: doc for doc in documents}
    findings = await run_document_sub_agent(user_message, doc_map, sections_by_doc)

    prompt_parts: list[str] = [
        "The following are research findings extracted from the documents.\n"
        "Each finding is prefixed with its source in the format "
        "[<filename>, <Section heading>].\n\n",
        f"<findings>\n{findings}\n</findings>\n\n",
        "When answering, cite the document filename and section heading for every "
        "claim you make, exactly as they appear in the findings above.\n\n",
    ]

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


async def _level3_chat(
    user_message: str,
    documents: list[DocContext],
    conversation_history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Level 3: semantic RAG — embed query, retrieve top-K chunks, stream answer."""
    all_chunks: list[dict[str, object]] = []

    for doc in documents:
        embedding_path = doc["embedding_path"]
        if not embedding_path:
            continue
        try:
            chunks = await retrieve_top_k_chunks(
                query=user_message,
                embedding_path=embedding_path,
                top_k=settings.rag_top_k,
            )
            for chunk in chunks:
                chunk["_filename"] = doc["filename"]
            all_chunks.extend(chunks)
        except Exception:
            logger.exception("RAG retrieval failed for doc", doc_id=doc["id"])

    prompt_parts: list[str] = []
    if all_chunks:
        prompt_parts.append(
            "The following sections were retrieved from the documents as most relevant "
            "to your query. Each is prefixed with its source.\n\n"
        )
        for chunk in all_chunks:
            filename = str(chunk.get("_filename") or "unknown")
            heading = str(chunk.get("heading") or f"Section {chunk.get('index', '?')}")
            content = str(chunk.get("content") or "")
            prompt_parts.append(f"[{filename}, {heading}]\n{content}\n\n")
        prompt_parts.append(
            "When answering, cite the document filename and section heading for every "
            "claim you make, exactly as they appear above.\n\n"
        )
    else:
        prompt_parts.append(
            "No relevant sections could be retrieved from the documents. "
            "Let the user know.\n\n"
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

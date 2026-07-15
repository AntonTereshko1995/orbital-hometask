from __future__ import annotations

from collections.abc import AsyncIterator

import litellm
import structlog

from ai.embeddings import retrieve_top_k_chunks
from ai.llm import API_KEY, MODEL
from ai.sub_agent import run_document_sub_agent
from ai.types import DocContext, SectionData
from config import settings

logger = structlog.get_logger()

_LEGAL_ASSISTANT_SYSTEM_PROMPT = (
    "You are a helpful legal document assistant for commercial real estate lawyers. "
    "You help lawyers review and understand documents during due diligence.\n\n"
    "IMPORTANT INSTRUCTIONS:\n"
    "- Answer questions based on the document content provided.\n"
    "- When referencing specific parts of the document, cite the relevant section or clause.\n"
    "- If the answer is not in the document, say so clearly. Do not fabricate information.\n"
    "- Be concise and precise. Lawyers value accuracy over verbosity.\n"
    "- When you reference specific content, mention the section, clause, or page.\n"
    "- When information comes from a specific document, always state the document name "
    "(e.g. 'According to commercial-lease-100-bishopsgate.pdf, Section 3...'). "
    "If answering from multiple documents, attribute each piece of information to its source document."
)


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
    """Stream a response, choosing a retrieval strategy based on document size.

    full_context:    all document text injected directly into the prompt.
    agentic_search:  a sub-agent navigates documents via tools and returns findings;
                     only those findings are included in the main prompt.
    semantic_rag:    user query is embedded; only the top-K semantically similar
                     chunks are injected into the main prompt.
    """
    total_tokens = estimate_tokens(documents)

    use_semantic_rag = total_tokens > settings.rag_token_threshold and any(
        doc["embedding_path"] for doc in documents
    )
    use_agentic_search = (
        not use_semantic_rag
        and total_tokens > settings.agentic_search_threshold
        and total_tokens < settings.rag_token_threshold
        and sections_by_doc is not None
        and bool(documents)
    )

    if use_semantic_rag:
        logger.info(
            "Routing decision",
            strategy="semantic_rag",
            total_tokens=total_tokens,
            threshold=settings.rag_token_threshold,
        )
        async for chunk in _stream_semantic_rag(user_message, documents, conversation_history):
            yield chunk
    elif use_agentic_search:
        logger.info(
            "Routing decision",
            strategy="agentic_search",
            total_tokens=total_tokens,
            threshold=settings.agentic_search_threshold,
        )
        async for chunk in _stream_agentic_search(
            user_message,
            documents,
            conversation_history,
            sections_by_doc,  # pyright: ignore[reportArgumentType]
        ):
            yield chunk
    else:
        logger.info(
            "Routing decision",
            strategy="full_context",
            total_tokens=total_tokens,
            threshold=settings.agentic_search_threshold,
        )
        async for chunk in _stream_full_context(user_message, documents, conversation_history):
            yield chunk


async def _stream_full_context(
    user_message: str,
    documents: list[DocContext],
    conversation_history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Inject all document text directly into the prompt and stream the response."""
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
        {"role": "system", "content": _LEGAL_ASSISTANT_SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt},
    ]

    stream = await litellm.acompletion(model=MODEL, messages=messages, stream=True, api_key=API_KEY)  # type: ignore[misc]  # pyright: ignore[reportUnknownMemberType]
    async for chunk in stream:  # type: ignore[union-attr]
        content = chunk.choices[0].delta.content  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
        if content:
            yield content


async def _stream_agentic_search(
    user_message: str,
    documents: list[DocContext],
    conversation_history: list[dict[str, str]],
    sections_by_doc: dict[str, list[SectionData]],
) -> AsyncIterator[str]:
    """Sub-agent explores documents via tools; findings feed into the main LLM."""
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
        {"role": "system", "content": _LEGAL_ASSISTANT_SYSTEM_PROMPT},
        {"role": "user", "content": full_prompt},
    ]

    stream = await litellm.acompletion(model=MODEL, messages=messages, stream=True, api_key=API_KEY)  # type: ignore[misc]  # pyright: ignore[reportUnknownMemberType]
    async for chunk in stream:  # type: ignore[union-attr]
        content = chunk.choices[0].delta.content  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
        if content:
            yield content


async def _stream_semantic_rag(
    user_message: str,
    documents: list[DocContext],
    conversation_history: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Embed query, retrieve top-K chunks by cosine similarity, stream answer."""
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
        {"role": "system", "content": _LEGAL_ASSISTANT_SYSTEM_PROMPT},
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

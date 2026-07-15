from __future__ import annotations

import json
from typing import Any

import litellm
import structlog

from ai.document_tools import TOOL_SCHEMAS, dispatch_tool
from ai.llm import API_KEY, MODEL
from ai.types import DocContext, SectionData
from config import settings

logger = structlog.get_logger()

_SUB_AGENT_SYSTEM_PROMPT = """\
You are a legal document research sub-agent. Your task is to find information \
relevant to the user's query by navigating document sections using the provided tools.

Follow this heuristic — work in order:
1. get_document_metadata for each document (understand size and structure)
2. get_document_outline to see section headings
3. search_document with key terms extracted from the query
4. read_document_section for sections that look relevant based on search results
5. Use read_document_chunk or read_document_head only when search yields no results
6. STOP and synthesise as soon as you have enough evidence — do NOT read everything

Output format — REQUIRED:
- For every fact or statement, prefix it with the source in square brackets:
  [<filename>, <Section heading or "Section <index>">]
- Example: [lease-agreement.pdf, Section 5 - Rent] The rent is £50,000 per annum...
- If a fact spans multiple sections, list all sources.
- Never omit the source prefix — the downstream model relies on it to cite documents.\
"""


async def run_document_sub_agent(
    user_query: str,
    doc_map: dict[str, DocContext],
    sections_by_doc: dict[str, list[SectionData]],
) -> str:
    """Run a tool-calling sub-agent that navigates documents and returns findings.

    The sub-agent iterates up to settings.sub_agent_max_iterations times, calling
    document tools to explore structure, search for keywords, and read relevant
    sections. It returns a condensed findings string for the main LLM to use.
    """
    doc_list = "\n".join(
        f"- {ctx['filename']} (id={did})" for did, ctx in doc_map.items()
    )
    messages: list[object] = [
        {"role": "system", "content": _SUB_AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Query: {user_query}\n\nAvailable documents:\n{doc_list}",
        },
    ]

    last_text: str = ""

    for iteration in range(settings.sub_agent_max_iterations):
        response = await litellm.acompletion(  # type: ignore[misc]
            model=MODEL,
            api_key=API_KEY,
            messages=messages,
            tools=TOOL_SCHEMAS,  # pyright: ignore[reportArgumentType]
        )

        choices: Any = getattr(response, "choices", [])  # pyright: ignore[reportUnknownMemberType]
        choice: Any = choices[0] if choices else None
        finish_reason: str = str(getattr(choice, "finish_reason", "") or "")
        message: Any = getattr(choice, "message", None)
        content: str = str(getattr(message, "content", "") or "")

        if content:
            last_text = content

        if finish_reason == "stop":
            logger.info(
                "Sub-agent finished",
                iterations=iteration + 1,
                findings_length=len(content),
            )
            return content

        tool_calls = getattr(message, "tool_calls", None)
        if finish_reason == "tool_calls" and tool_calls:
            messages.append(message)  # pyright: ignore[reportArgumentType]
            for tc in tool_calls:
                fn_name: str = str(getattr(getattr(tc, "function", None), "name", ""))
                fn_args_raw: str = str(
                    getattr(getattr(tc, "function", None), "arguments", "{}")
                )
                tc_id: str = str(getattr(tc, "id", ""))
                try:
                    args: dict[str, Any] = json.loads(fn_args_raw)
                except json.JSONDecodeError:
                    args = {}
                result_str = dispatch_tool(fn_name, args, doc_map, sections_by_doc)
                logger.debug("Tool call", tool=fn_name, doc_id=args.get("doc_id"))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": result_str,
                    }
                )
        else:
            logger.warning(
                "Sub-agent unexpected finish_reason",
                finish_reason=finish_reason,
                iteration=iteration,
            )
            break

    logger.warning(
        "Sub-agent hit iteration limit",
        max_iterations=settings.sub_agent_max_iterations,
    )
    return last_text or "Could not find relevant information within the iteration limit."

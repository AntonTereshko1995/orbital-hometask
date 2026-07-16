from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai.sub_agent import run_document_sub_agent
from ai.types import DocContext, SectionData

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

DOC_MAP: dict[str, DocContext] = {
    "d1": {
        "id": "d1",
        "filename": "commercial-lease.pdf",
        "text": "Full lease text here.",
        "embedding_path": None,
    }
}

SECTIONS_BY_DOC: dict[str, list[SectionData]] = {
    "d1": [
        {
            "id": "s0",
            "doc_id": "d1",
            "index": 0,
            "heading": "Definitions",
            "content": "The Lessee shall pay monthly rent.",
            "token_count": 7,
        }
    ]
}


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def _stop_response(content: str = "findings here") -> MagicMock:
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message.content = content
    choice.message.tool_calls = None
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _tool_call_response(
    fn_name: str = "get_document_outline",
    fn_args: str = '{"doc_id": "d1"}',
    tc_id: str = "tc001",
) -> MagicMock:
    tc = MagicMock()
    tc.id = tc_id
    tc.function.name = fn_name
    tc.function.arguments = fn_args

    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message.content = ""
    choice.message.tool_calls = [tc]

    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_returns_content_on_stop() -> None:
    with patch(
        "ai.sub_agent.litellm.acompletion",
        new_callable=AsyncMock,
        return_value=_stop_response("my findings"),
    ):
        result = await run_document_sub_agent("What is the rent?", DOC_MAP, SECTIONS_BY_DOC)

    assert result == "my findings"


async def test_executes_tool_call_then_stops() -> None:
    responses = [
        _tool_call_response("get_document_outline", '{"doc_id": "d1"}', "tc001"),
        _stop_response("final findings after tool"),
    ]
    with patch(
        "ai.sub_agent.litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=responses,
    ):
        result = await run_document_sub_agent("What is the rent?", DOC_MAP, SECTIONS_BY_DOC)

    assert result == "final findings after tool"


async def test_hits_iteration_limit_returns_last_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force sub_agent_max_iterations=1 so the loop exits after one non-stop response.
    mock_settings = MagicMock()
    mock_settings.sub_agent_max_iterations = 1
    monkeypatch.setattr("ai.sub_agent.settings", mock_settings)

    # Single tool_calls response (no stop) → loop exits at limit
    with patch(
        "ai.sub_agent.litellm.acompletion",
        new_callable=AsyncMock,
        return_value=_tool_call_response(),
    ):
        result = await run_document_sub_agent("query", DOC_MAP, SECTIONS_BY_DOC)

    # Returns the fallback string when no stop was received
    assert isinstance(result, str)
    assert len(result) > 0


async def test_invalid_json_in_tool_args_does_not_raise() -> None:
    tc = MagicMock()
    tc.id = "tc001"
    tc.function.name = "get_document_outline"
    tc.function.arguments = "INVALID {{ json"

    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message.content = ""
    choice.message.tool_calls = [tc]

    bad_json_resp = MagicMock()
    bad_json_resp.choices = [choice]

    responses = [bad_json_resp, _stop_response("recovered")]
    with patch(
        "ai.sub_agent.litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=responses,
    ):
        result = await run_document_sub_agent("query", DOC_MAP, SECTIONS_BY_DOC)

    assert result == "recovered"


async def test_unknown_tool_name_returns_error_json_and_continues() -> None:
    responses = [
        _tool_call_response("nonexistent_tool", '{"doc_id": "d1"}'),
        _stop_response("done after unknown tool"),
    ]
    with patch(
        "ai.sub_agent.litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=responses,
    ):
        result = await run_document_sub_agent("query", DOC_MAP, SECTIONS_BY_DOC)

    assert result == "done after unknown tool"


async def test_empty_doc_map_still_returns_string() -> None:
    with patch(
        "ai.sub_agent.litellm.acompletion",
        new_callable=AsyncMock,
        return_value=_stop_response("nothing found"),
    ):
        result = await run_document_sub_agent("query", {}, {})

    assert isinstance(result, str)
    assert result == "nothing found"

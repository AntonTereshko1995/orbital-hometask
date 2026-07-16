from __future__ import annotations

import os

# Must be set before any SQLAlchemy/FastAPI imports so create_async_engine gets
# a valid URL. The engine is never actually used in tests (all repos are mocked).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/testdb")

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from db.session import get_session
from web.app import app
from web.routers import conversations as conv_router
from web.routers import documents as doc_router
from web.routers import messages as msg_router

_TS = datetime(2024, 1, 1, 12, 0, 0)


# ---------------------------------------------------------------------------
# ORM-object builder helpers
# All attributes are concrete values so Pydantic response_model serialization
# does not 500 on MagicMock auto-attributes.
# ---------------------------------------------------------------------------


def _conv(
    id: str = "conv0000001test",
    title: str = "Test Conversation",
    documents: list | None = None,
) -> MagicMock:
    m = MagicMock()
    m.id = id
    m.title = title
    m.documents = documents if documents is not None else []
    m.created_at = _TS
    m.updated_at = _TS
    return m


def _doc(
    id: str = "doc0000000001",
    conversation_id: str = "conv0000001test",
    filename: str = "test.pdf",
    file_path: str = "/tmp/test.pdf",
) -> MagicMock:
    m = MagicMock()
    m.id = id
    m.conversation_id = conversation_id
    m.filename = filename
    m.page_count = 5
    m.file_path = file_path
    m.extracted_text = "Full document text."
    m.embedding_path = None
    m.created_at = _TS
    return m


def _msg(
    id: str = "msg0000000001",
    role: str = "assistant",
    content: str = "Test response",
    sources_cited: int = 0,
) -> MagicMock:
    m = MagicMock()
    m.id = id
    m.conversation_id = "conv0000001test"
    m.role = role
    m.content = content
    m.sources_cited = sources_cited
    m.created_at = _TS
    return m


# ---------------------------------------------------------------------------
# Repository fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conversation() -> MagicMock:
    return _conv()


@pytest.fixture
def mock_conv_repo(conversation: MagicMock) -> MagicMock:
    repo = MagicMock()
    repo.get = AsyncMock(return_value=conversation)
    repo.list = AsyncMock(return_value=[conversation])
    # Return pre-configured mock so Pydantic serialization works regardless of
    # whether SQLAlchemy applies column defaults at construction time.
    repo.save = AsyncMock(return_value=conversation)
    repo.delete = AsyncMock(return_value=True)
    repo.update_title = AsyncMock(return_value=conversation)
    return repo


@pytest.fixture
def mock_doc_repo() -> MagicMock:
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    repo.list_for_conversation = AsyncMock(return_value=[])
    repo.save = AsyncMock(return_value=_doc())
    return repo


@pytest.fixture
def mock_msg_repo() -> MagicMock:
    repo = MagicMock()
    repo.list_for_conversation = AsyncMock(return_value=[])
    repo.list_history = AsyncMock(return_value=[])
    # side_effect returns the argument so user_message.id is available for logging
    repo.save = AsyncMock(side_effect=lambda x: x)
    return repo


@pytest.fixture
def mock_section_repo() -> MagicMock:
    repo = MagicMock()
    repo.list_for_document = AsyncMock(return_value=[])
    return repo


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(
    mock_conv_repo: MagicMock,
    mock_doc_repo: MagicMock,
    mock_msg_repo: MagicMock,
    mock_section_repo: MagicMock,
) -> AsyncClient:
    """httpx.AsyncClient wired to the FastAPI app with all DB deps mocked.

    Uses ASGITransport which does NOT trigger the lifespan context manager,
    so Alembic migrations never run and no real database is needed.
    """

    async def _fake_session():  # type: ignore[return]
        yield MagicMock()

    app.dependency_overrides = {
        conv_router.get_conversation_repo: lambda: mock_conv_repo,
        msg_router.get_conversation_repo: lambda: mock_conv_repo,
        doc_router.get_conversation_repo: lambda: mock_conv_repo,
        msg_router.get_document_repo: lambda: mock_doc_repo,
        doc_router.get_document_repo: lambda: mock_doc_repo,
        msg_router.get_message_repo: lambda: mock_msg_repo,
        msg_router.get_section_repo: lambda: mock_section_repo,
        get_session: _fake_session,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c  # type: ignore[misc]

    app.dependency_overrides.clear()

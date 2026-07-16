# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Orbital is a document Q&A tool for commercial real estate lawyers. Users upload PDF legal documents per conversation and ask questions about them. The AI answers based on document content, streamed via SSE.

## Commands

All commands run code inside Docker containers. The stack requires Docker and `just`.

```bash
just setup            # First-time setup: copy .env, build images
just dev              # Start full stack (Postgres + backend + frontend) with hot reload
just dev-debug        # Start with debugpy on port 5678 (attach via VS Code "Docker: Attach Backend")
just stop             # Stop all services
just reset            # Stop and wipe database volume

just check            # Run all linters and type checks (backend + frontend)
just fmt              # Format all code

just check-backend    # ruff + pyright on backend/src/
just check-frontend   # biome check + tsc on frontend/src/
just fmt-backend      # ruff format + ruff check --fix
just fmt-frontend     # biome format --write

just db-migrate "message"   # Generate a new Alembic migration
just db-upgrade             # Apply pending migrations
just db-shell               # Open psql shell

just logs             # Tail all service logs
just logs-backend     # Tail backend logs only
just shell-backend    # bash into the backend container
just shell-frontend   # bash into the frontend container

just add-dep <package>          # Add Python dependency (uv add inside container)
just add-dep-frontend <package> # Add npm dependency
```

Run backend tests inside the container (no real database needed — all repos are mocked):
```bash
docker compose exec backend uv run pytest
docker compose exec backend uv run pytest backend/tests/test_pipeline.py  # single file
```

## Architecture

### Three-layer layout

```
frontend/src/   React 18 + Vite + TypeScript + Tailwind + Biome
backend/src/    FastAPI + Python 3.12 + SQLAlchemy async + LiteLLM
alembic/        Database migrations (PostgreSQL 16 via asyncpg)
```

`PYTHONPATH=/app/backend/src` is set in the Dockerfile, so all imports are relative to `backend/src/` — e.g., `from db.models import Document`, `from ai.pipeline import chat_with_document`.

### Backend (`backend/src/`)

**`config.py`** — Pydantic `Settings` reads `.env`. Key fields: `llm_api_key`, `llm_model`, `embedding_model`, `embedding_api_key`, `agentic_search_threshold` (default 1 000 tokens), `rag_token_threshold` (default 10 000 tokens), `rag_top_k`.

**`db/`**
- `models/` — Four SQLAlchemy ORM models: `Conversation`, `Message`, `Document`, `DocumentSection`. IDs are 16-char hex UUIDs. `DocumentSection` stores parsed sections (heading, content, token_count) for agentic search.
- `repository.py` — Generic `BaseRepository[ModelT]` with `get`, `list`, `save`, `delete`.
- `repositories/` — Per-model repos extending `BaseRepository`: `ConversationRepository`, `DocumentRepository`, `DocumentSectionRepository`, `MessageRepository`.
- `session.py` — Async engine + `async_session` factory. FastAPI DI uses `get_session()`.

**`services/`**
- `document.py` — PDF upload pipeline: validates, saves to `uploads/`, extracts text via **MarkItDown** (page count via pypdf), stores in DB, indexes sections, generates embeddings.
- `document_index.py` — `parse_sections()` splits extracted text into `ParsedSection` objects.
- `embedding_store.py` — Manages embedding JSON files under `uploads/embeddings/`.

**`ai/`**
- `llm.py` — Exports `MODEL` and `API_KEY` from settings. Must be imported before LiteLLM makes its first call.
- `pipeline.py` — `chat_with_document()` routes to one of three strategies based on token count, then streams via LiteLLM. Also `generate_title()` for auto-naming conversations.
- `sub_agent.py` — Agentic document search loop (up to `sub_agent_max_iterations` tool calls).
- `document_tools.py` — Tools available to the sub-agent.
- `embeddings.py` — `generate_and_save_embeddings()` and `retrieve_top_k_chunks()` (cosine similarity).
- `analysis.py` — `count_sources_cited()` regex-counts section/clause/page references.
- `types.py` — Shared `TypedDict` types: `DocContext`, `SectionData`.

**`web/`**
- `app.py` — FastAPI app; runs Alembic `upgrade head` on startup via `asyncio.to_thread`.
- `routers/conversations.py`, `routers/documents.py`, `routers/messages.py` — API endpoints.
- `schemas/` — Pydantic request/response models (separate from ORM models).

### Three-strategy retrieval pipeline (`ai/pipeline.py`)

`chat_with_document()` picks a strategy per-request by token-counting all document text:

| Strategy | Condition | Behaviour |
|---|---|---|
| `full_context` | tokens ≤ `agentic_search_threshold` | All document text injected into the prompt |
| `agentic_search` | `agentic_search_threshold` < tokens < `rag_token_threshold` and sections exist | Sub-agent explores sections via tools; findings injected into the main prompt |
| `semantic_rag` | tokens ≥ `rag_token_threshold` and embedding file exists | Query is embedded; top-K chunks by cosine similarity injected |

All three strategies stream via `litellm.acompletion(..., stream=True)`.

### Frontend (`frontend/src/`)

Three-pane layout in `App.tsx`: `ChatSidebar` | `ChatWindow` | `DocumentViewer`.

- **`lib/api.ts`** — All API calls. Vite proxies `/api/*` to the backend container.
- **`lib/sse.ts`** — SSE event parsing.
- **`hooks/`** — `use-conversations`, `use-messages`, `use-document` manage state and API interactions.
- **`types.ts`** — Shared TypeScript interfaces (`Conversation`, `Message`, `Document`, `ConversationDetail`).

### SSE streaming protocol

The `POST /api/conversations/{id}/messages` endpoint returns `text/event-stream`. Each SSE event is a JSON object:
- `{"type": "content", "content": "<chunk>"}` — incremental text chunk
- `{"type": "message", "message": {...}}` — full saved assistant message
- `{"type": "done", "sources_cited": N, "message_id": "..."}` — stream complete

The SSE generator in `messages.py` opens its own DB sessions for post-stream writes (after the request-scoped session closes).

### Data model constraints

- Each conversation holds exactly one document (enforced at upload time).
- Uploaded files are stored on disk under `uploads/` (volume-mounted in Docker); embedding JSON files live under `uploads/embeddings/`.
- `Message.sources_cited` counts regex matches of section/clause/page references.
- Alembic migrations auto-run on startup; never apply them manually in production.

### Testing

Tests live in `backend/tests/`. All database interactions are mocked — no real DB is needed. `conftest.py` provides `mock_conv_repo`, `mock_doc_repo`, `mock_msg_repo`, `mock_section_repo`, and an `httpx.AsyncClient` (`client`) wired to the FastAPI app via `ASGITransport` (which skips the lifespan hook, so Alembic never runs).

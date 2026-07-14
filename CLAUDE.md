# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Orbital is a document Q&A tool for commercial real estate lawyers. Users upload PDF legal documents per conversation and ask questions about them. The AI answers based on document content, streamed via SSE.

## Commands

All commands run code inside Docker containers. The stack requires Docker and `just`.

```bash
just dev              # Start full stack (Postgres + backend + frontend) with hot reload
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

just add-dep <package>          # Add Python dependency (uv add inside container)
just add-dep-frontend <package> # Add npm dependency
```

Run backend tests inside the container:
```bash
docker compose exec backend uv run pytest
```

## Architecture

### Three-layer layout

```
frontend/src/   React 18 + Vite + TypeScript + Tailwind + Biome
backend/src/    FastAPI + Python 3.12 + SQLAlchemy async + PydanticAI
alembic/        Database migrations (PostgreSQL 16 via asyncpg)
```

### Backend (`backend/src/`)

`PYTHONPATH=/app/backend/src` is set in the Dockerfile, so all imports are relative to `backend/src/` — e.g., `from db.models import Document`, `from services.llm import chat_with_document`.

- **`config.py`** — Pydantic `Settings` reads `.env`; also exports `ANTHROPIC_API_KEY` to the environment for PydanticAI.
- **`db/models.py`** — Three SQLAlchemy ORM models: `Conversation`, `Message`, `Document`. One document per conversation (enforced in `services/document.py`). IDs are 16-char hex UUIDs.
- **`db/session.py`** — Async engine + `async_session` factory. FastAPI DI uses `get_session()`.
- **`services/llm.py`** — PydanticAI `Agent` wrapping `anthropic:claude-haiku-4-5-20251001`. `chat_with_document()` builds a single prompt string containing the full document text, conversation history, and current message, then streams the response. `count_sources_cited()` regex-counts section/clause/page references in assistant replies.
- **`services/document.py`** — PDF upload: validates type/size, saves to `uploads/`, extracts text with PyMuPDF (`fitz`), stores in DB.
- **`web/app.py`** — FastAPI app; runs Alembic `upgrade head` automatically on startup via `asyncio.to_thread` (Alembic uses sync APIs).
- **`web/routers/messages.py`** — `POST /api/conversations/{id}/messages` saves the user message, streams the LLM response as SSE (`text/event-stream`), then saves the assistant message and (on first message) auto-generates a conversation title — all inside the `event_stream()` async generator.

### Frontend (`frontend/src/`)

Three-pane layout in `App.tsx`: `ChatSidebar` | `ChatWindow` | `DocumentViewer`.

- **`lib/api.ts`** — All API calls. Vite proxies `/api/*` to the backend container.
- **`hooks/`** — `use-conversations`, `use-messages`, `use-document` manage state and API interactions.
- **`types.ts`** — Shared TypeScript interfaces (`Conversation`, `Message`, `Document`, `ConversationDetail`).

### SSE streaming protocol

The `POST /messages` endpoint returns `text/event-stream`. Each SSE event is a JSON object with a `type` field:
- `{"type": "content", "content": "<chunk>"}` — incremental text chunk
- `{"type": "message", "message": {...}}` — full saved assistant message
- `{"type": "done", "sources_cited": N, "message_id": "..."}` — stream complete

### Data model constraints

- Each conversation holds exactly one document (enforced at upload time).
- `Message.sources_cited` counts regex matches of section/clause/page references in the assistant response.
- Uploaded files are stored on disk under `uploads/` (volume-mounted in Docker).

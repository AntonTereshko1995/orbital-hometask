# Orbital — Document Q&A for Commercial Real Estate Lawyers

A document Q&A tool that lets lawyers upload legal documents (leases, title reports, environmental assessments) and ask questions grounded in the document content. The AI assistant streams answers in real time, cites the specific sections it draws from, and handles everything from a single short clause schedule to a multi-document portfolio acquisition.

---

## Loom walkthrough

<!-- TODO: paste Loom link here before submission -->

---

## Setup

### Prerequisites

- Docker and Docker Compose
- `just` — `brew install just` or `cargo install just`

Everything else runs inside containers.

### Getting started

```bash
git clone <your-repo>
cd orbital-hometask
just setup          # copies .env.example → .env and builds images
```

Open `.env` and fill in the two required keys:

```env
LLM_API_KEY=your_anthropic_api_key
EMBEDDING_API_KEY=your_openai_api_key   # only needed for Level 3 RAG
```

```bash
just dev            # starts Postgres + backend (8000) + frontend (5173)
```

Open [http://localhost:5173](http://localhost:5173). Migrations run automatically on startup.

### Useful commands

| Command                                       | What it does                         |
| --------------------------------------------- | ------------------------------------ |
| `just dev`                                    | Start the full stack with hot reload |
| `just stop`                                   | Stop all services                    |
| `just reset`                                  | Stop + wipe the database volume      |
| `just check`                                  | Ruff + Pyright + Biome + tsc         |
| `just fmt`                                    | Auto-format backend and frontend     |
| `just db-migrate "msg"`                       | Generate a new Alembic migration     |
| `just db-upgrade`                             | Apply pending migrations             |
| `just db-shell`                               | Open a psql shell                    |
| `docker compose exec backend uv run pytest`   | Run the backend test suite           |

### Sample documents

`sample-docs/` contains sample legal PDFs for testing.

---

## What I built

### Part 1 — Multi-document conversations

Conversations can now hold any number of documents. The key changes:

- **Upload flow** — the document upload button remains available throughout the conversation; users can keep adding files without starting a new chat.
- **Document tabs** — when more than one document is loaded, a tab bar appears in the document viewer so users can switch between them. The active tab persists across messages.
- **Multi-file picker** — the file input accepts multiple files in one pick, and each uploads in sequence.
- **LLM context** — all loaded documents are passed to the AI together, each wrapped in a `<document name="…">` tag. The system prompt instructs the model to attribute every claim to its source document by name, enabling cross-document comparison questions ("how does the indemnity clause in the lease compare to the purchase agreement?").

### Part 2 — Three-level retrieval pipeline

This is the main engineering investment. The data and feedback both pointed at the same root cause: **hallucinations and vague answers destroy trust faster than anything else**. A senior partner said it directly — *"being confidently wrong is worse than being slow."*

The baseline implementation dumped the entire document into the prompt on every query. That works for short documents but degrades on large ones: the model loses precision, starts confabulating, and context windows fill up. I replaced it with an adaptive three-level pipeline that routes each query to the cheapest strategy that can still answer accurately:

#### Level 1 — Full context (< ~1 000 tokens)

Short documents (clause schedules, short letters) are injected verbatim. Fast, zero overhead, accurate.

#### Level 2 — Agentic search (~1 000 – 9 000 tokens)

Documents are split into sections at upload time using a heading parser tuned to legal structure (Section N, ARTICLE, Schedule headings, with paragraph-budget fallback). A sub-agent receives the user question and a toolkit — `get_metadata`, `search_sections`, `get_outline`, `read_section` — and iterates until it has gathered enough evidence. Only the retrieved findings are passed to the main model, not the entire document. This keeps the final prompt tight and forces every sentence to be grounded in a named section.

#### Level 3 — Semantic RAG (> 9 000 tokens)

Large documents generate text embeddings at upload time (via LiteLLM, defaulting to `openai/text-embedding-3-small`). The embeddings are stored as JSON on disk alongside the document. At query time the question is embedded and the top-K most similar chunks are retrieved by cosine similarity. Only those chunks reach the main model.

The routing logic lives in [`backend/src/ai/pipeline.py`](backend/src/ai/pipeline.py). Thresholds are configurable via env vars (`AGENTIC_SEARCH_THRESHOLD`, `RAG_TOKEN_THRESHOLD`, `RAG_TOP_K`).

### Part 3 — Product improvements driven by feedback

After completing the retrieval pipeline I went back to the feedback and picked off the next clearest user problems.

#### Document library

One beta user said: *"I had to re-upload the same lease agreement in three different chats because I was asking different types of questions about it each time. Feels like the tool should just remember my documents."*

The library panel lets users upload a PDF once and attach it to any number of conversations without re-uploading. The backend deduplicates by content hash (SHA-256) so the same file is never stored twice even if uploaded again. The conversation ↔ document relationship is now M:N.

#### Improved PDF viewer

Switched from the custom viewer to `react-pdf-viewer` with a resizable split-pane layout. The document panel can be dragged to any width, which matters when you want to read a long clause and the AI answer side by side.

#### Conversation pinning

Pinned conversations float to the top of the sidebar list. Useful for active matters that a lawyer returns to daily across a longer due diligence process.

#### Read-only sharing

Any conversation can be shared via a unique link. The shared view is fully read-only — no API key required to load it, no ability to send messages. Useful for passing a Q&A thread to a colleague or client without giving them access to the account.

---

## Other changes from the baseline

### LiteLLM instead of PydanticAI

I swapped `pydantic-ai-slim[anthropic]` for [LiteLLM](https://github.com/BerriAI/litellm). Two reasons:

1. **Provider flexibility** — `LLM_MODEL` and `LLM_API_KEY` are env vars; switching from Anthropic to xAI, OpenAI, or a local Ollama instance requires no code changes.
2. **Uniform async streaming** — `litellm.acompletion(..., stream=True)` works identically across providers, which matters when the three pipeline levels may use different models.

### MarkItDown instead of PyMuPDF

I replaced PyMuPDF (`fitz`) with [MarkItDown](https://github.com/microsoft/markitdown) for document extraction:

- **Licence** — PyMuPDF is AGPL-3.0, which prohibits use in closed-source commercial products without a commercial licence. MarkItDown is MIT.
- **LLM accuracy** — Markdown preserves headings, lists, and table structure. The legal documents in the sample set have clear hierarchical headings; extracting them as Markdown rather than raw text means the section parser (and the model itself) can navigate the document structure rather than treating it as one flat string.

### Repository pattern

Service functions were replaced with typed repository classes (`ConversationRepository`, `DocumentRepository`, `MessageRepository`, `DocumentSectionRepository`) injected via FastAPI's dependency injection. Database query logic is no longer spread across router files.

### Backend test suite

Added ~2 000 lines of unit and integration tests across 13 test files covering API endpoints, document processing, the section indexer, the sub-agent tool loop, the embedding store, all three pipeline routing strategies, document library deduplication, and conversation sharing.

---

## Architecture overview

```
frontend/src/     React 18 + Vite + TypeScript + Tailwind + Biome
backend/src/
  ai/             LLM pipeline, sub-agent, embeddings, document tools
  db/             SQLAlchemy models, repositories, session factory
  services/       Document processing, section indexing, embedding store
  web/            FastAPI app, routers, Pydantic schemas
    routers/      conversations, documents, messages, sharing, storage
alembic/          PostgreSQL migrations
```

Environment variables (full list in `.env.example`):

| Variable                     | Purpose                                                                      |
| ---------------------------- | ---------------------------------------------------------------------------- |
| `LLM_API_KEY`                | API key for the main LLM (Anthropic, OpenAI, …)                             |
| `LLM_MODEL`                  | LiteLLM model string, e.g. `anthropic/claude-haiku-4-5-20251001`            |
| `EMBEDDING_MODEL`            | Embedding model for Level 3 RAG (default: `openai/text-embedding-3-small`)  |
| `EMBEDDING_API_KEY`          | API key for the embedding model                                              |
| `AGENTIC_SEARCH_THRESHOLD`   | Token count above which Level 2 activates (default: 1 000)                  |
| `RAG_TOKEN_THRESHOLD`        | Token count above which Level 3 activates (default: 10 000)                 |
| `RAG_TOP_K`                  | Number of chunks retrieved in Level 3 (default: 10)                         |

---

## Decisions

### Why the retrieval pipeline over other options

The customer feedback had several themes — export to Word, annotation, Ctrl+F search — but one signal was louder than all the others: **hallucinations**. Two partners used the word "terrifying". One associate stopped using the product entirely after a single fabricated clause. An associate put the value proposition most clearly: *"When the AI tells me it's from section 4.2, it's magic. When it doesn't cite anything, I have to go find it myself anyway — so what's the point?"*

That framing made the decision easy. Annotation and export are quality-of-life features. Fixing hallucinations is the feature that determines whether lawyers trust the tool at all. Everything else is moot if the answer can't be trusted.

The usage data reinforced this: sessions with more than three prompts were rare, suggesting users were abandoning conversations after getting an answer they couldn't verify. A retrieval architecture that forces citation back to a named section is both the fix and the proof — lawyers can see exactly where each claim came from.

### Why three levels instead of RAG-only

Pure RAG (always embed, always retrieve) would solve the accuracy problem for large documents but would be overkill — and slower — for the short clause schedules and letters that make up a large share of real-estate due diligence. The adaptive router keeps the fast path fast and only pays the cost of embedding and retrieval when the document is big enough to warrant it.

### What I'd do next

In production I'd replace the disk-backed JSON embedding store with a proper vector database (ChromaDB for a managed option).

I'd add a confidence indicator to the UI — a clear ask from the feedback — surfaced as a simple "high / medium / low certainty" label on each answer, derived from the retrieval similarity scores. That addresses the partner who said they'd *"pay double the licence fee"* for an AI that admits uncertainty.

I'd also expose the model's reasoning process in the UI — an expandable "thinking" panel that shows the sub-agent's tool calls as they happen (which sections it searched, what it read, why it moved on). This turns the black-box answer into an auditable trace, which is exactly what a lawyer needs before staking a client opinion on it. Extended thinking is supported by Claude's latest models and can be streamed through the existing SSE channel.

Finally, the current UI/UX still has room to grow. The three areas I'd prioritise: a Ctrl+F / jump-to-section search within the document viewer (explicitly requested in feedback), inline highlighting that scrolls the viewer to the cited section when the user clicks a reference in the chat, and an export-to-Word flow for the conversation summary. These together close the loop between "AI found the answer" and "lawyer can share it with a client."

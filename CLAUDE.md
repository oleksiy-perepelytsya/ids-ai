# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IDS (Intelligent Development System) is a multi-agent AI deliberation platform. It implements a "Parliament" architecture where specialist agents (Gemini) + generalist agent (Claude) debate questions and reach consensus using CROSS scoring (Confidence, Risk, Outcome, Standard deviation).

**Budget target:** $10/month. Gemini handles ~90% of operations; Claude handles ~10% critical decisions.

## Roadmap

- **Phase 1** — Deliberation engine ✅ (parliament, CROSS scoring, consensus, knowledge base)
- **Phase 2** — Interfaces, prompts, projects, role models 🔧 (active)
  - ✅ Abstract interface layer (`InterfaceAdapter` protocol, `CommandHandler`)
  - ✅ Telegram adapter
  - ✅ CLI REPL adapter
  - ✅ Project model with per-project prompt configs and specialist roles
  - ✅ Prompt loader (URL + local fallback)
  - ✅ Hostess agent (app assistant)
  - ⬜ Web interface
  - ⬜ Email interface
  - ⬜ Generic prompt library
  - ⬜ Role models management
- **Phase 3** — MCP server & data sources ⬜
  - MCP server with management system
  - Connect databases and external data sources (app-wide or per-project)
  - Include data sources in agent workflows
- **Phase 4** — Claude Code / CLI integration ⬜ (lowest priority, not implemented)
  - Post-consensus implementation via `claude -p`
  - Direct `/code` command
  - Note: exploratory code exists (`claude_code.py`, `code_workflow.py`) — should be removed

## Commands

```bash
poetry install && python -m ids              # Telegram (default)
python -m ids --interface cli                 # CLI REPL
docker compose -f docker-compose.dev.yml up   # Docker dev
docker compose up                             # Docker prod
poetry run ruff check ids/ && poetry run ruff format ids/  # Lint
poetry run mypy ids/                          # Type check
poetry run pytest                             # Tests (not yet implemented)
```

## Architecture

```
User ──→ InterfaceAdapter ──→ CommandHandler ──→ SessionManager → RoundExecutor
         (Telegram/CLI/…)    (business logic)                          ↓
                                                          ConsensusBuilder ← Agents (via LLMClient)
                                                                           ↓
                                                         MongoDB (sessions) + Qdrant (vector search)
```

### Search Architecture

```
Callers (RoundExecutor, SessionManager, HostessContext)
                         │
               SearchOrchestrator   ← single entry point
                         │
           reads project.data_sources[]
           fans out to backends, merges hits
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        QdrantBackend  GraphBackend  (future)
              │        (Phase 3 stub)
           Qdrant
```

- **`ids/search/backend.py`** — `SearchBackend` protocol, `SearchHit`, `VectorDoc`
- **`ids/search/orchestrator.py`** — `SearchOrchestrator` (replaces ChromaStore)
- **`ids/search/embeddings.py`** — `EMBEDDING_REGISTRY` + `EmbeddingSpec`
- **`ids/search/data_source.py`** — `DataSource` model (per-project search config)
- **`ids/search/manifests.py`** — `CorpusManifest` (dataset metadata in MongoDB)
- **`ids/search/backends/qdrant.py`** — `QdrantBackend` (named vectors, nested payloads)
- **`ids/search/backends/graph.py`** — `GraphBackend` stub (Phase 3)

### Key Components

- **`ids/interfaces/base.py`** — Abstract `InterfaceAdapter` protocol + `Message`/`Reply` value objects
- **`ids/interfaces/command_handler.py`** — Transport-agnostic command handler (all business logic)
- **`ids/interfaces/telegram/adapter.py`** — Telegram adapter
- **`ids/interfaces/cli/adapter.py`** — CLI REPL adapter
- **`ids/agents/base_agent.py`** — Unified `Agent` class; behavior driven by persona markdown files in `ids/agents/personas/`
- **`ids/services/llm_client.py`** — Unified client for Gemini and Anthropic APIs
- **`ids/services/prompt_loader.py`** — Fetches prompts from URL or local fallback
- **`ids/orchestrator/`** — `SessionManager`, `RoundExecutor`, `ConsensusBuilder`
- **`ids/config/settings.py`** — Pydantic Settings (`.env`)
- **`ids/config/thresholds.yaml`** — Consensus scoring thresholds
- **`ids/storage/mongo_store.py`** — MongoDB (sessions, projects, corpus_manifests, corpus_docs)
- **`ids/models/project.py`** — Project model with per-project prompts, specialist roles, data sources

### Agent Roles

Defined by persona files in `ids/agents/personas/` (markdown with `# Role:` and `# System Prompt`):
- **Generalist** (Claude) — Facilitator, frames problems, does not proppse solutions
- **Specialists** (Gemini) — Various specialist setups including generic prompts
- **Sourcer** (Gemini) — Knowledge base search, single answering agent
- **Hostess** (Gemini) — App assistant, helps users navigate IDS

## Code Conventions

- **Async-first:** All I/O uses async/await
- **Pydantic models** for all data structures (`ids/models/`)
- **Structured logging** via `structlog` with JSON output
- **Type hints** on all function signatures
- **Configuration** via environment variables through Pydantic Settings
- **Ruff** for linting (line-length: 100, Python 3.11 target)
- **No mocks in tests** — use real services
- **Agent personas** are markdown files, not code

## Infrastructure

Docker Compose: MongoDB 7, Qdrant (vector search), Redis 7 (optional caching).

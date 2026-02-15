# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IDS (Intelligent Development System) is a multi-agent AI deliberation platform accessed via Telegram. It implements a "Parliament" architecture where 6 specialist agents (Gemini 2.0 Flash) + 1 generalist agent (Claude Sonnet 4) debate questions and reach consensus using CROSS scoring (Confidence, Risk, Outcome, Standard deviation).

**Budget target:** $10/month. Gemini handles ~90% of operations; Claude handles ~10% critical decisions.

**Status:** Phase 1 complete (deliberation), Phase 2 in progress (code generation, file ops, git integration).

## Commands

```bash
# Run locally
poetry install
python -m ids

# Run with Docker (dev - builds locally, mounts code for live reload)
docker compose -f docker-compose.dev.yml up

# Run with Docker (prod - pulls from GHCR)
docker compose up

# Lint
poetry run ruff check ids/
poetry run ruff format ids/

# Type check
poetry run mypy ids/

# Tests (test directory exists but tests are not yet implemented)
poetry run pytest
```

## Architecture

### Deliberation Flow
```
User (Telegram) → Bot Handlers → SessionManager → RoundExecutor
                                                        ↓
                                             ConsensusBuilder ← Agents (via LLMClient)
                                                        ↓
                                      MongoDB (sessions) + ChromaDB (learned patterns)
```

1. User submits a question via Telegram
2. `SessionManager` creates a session with project context
3. `RoundExecutor` runs up to `MAX_ROUNDS` (default 3) deliberation rounds:
   - Generalist (Claude) frames the problem without proposing solutions
   - Specialists (Gemini) respond with CROSS scores + analysis
   - `ConsensusBuilder` evaluates scores against thresholds in `ids/config/thresholds.yaml`
4. Result: consensus reached, dead-end detected, or user feedback requested
5. Successful patterns stored in ChromaDB for future retrieval

### Key Components

- **`ids/agents/base_agent.py`** — Single unified `Agent` class for all agents. Behavior differentiated by persona markdown files in `ids/agents/personas/`.
- **`ids/services/llm_client.py`** — Unified client wrapping both Gemini and Anthropic APIs. Routes requests based on agent role.
- **`ids/orchestrator/session_manager.py`** — Session lifecycle orchestration.
- **`ids/orchestrator/round_executor.py`** — Executes individual deliberation rounds, manages agent execution (parallel or sequential based on `PARALLEL_AGENTS` env var).
- **`ids/orchestrator/consensus_builder.py`** — Evaluates CROSS scores against configurable thresholds.
- **`ids/config/settings.py`** — Pydantic Settings loading all configuration from `.env`.
- **`ids/storage/mongo_store.py`** — MongoDB persistence for sessions and projects.
- **`ids/storage/chroma_store.py`** — ChromaDB vector store for knowledge base / learned patterns.
- **`ids/interfaces/telegram/`** — Bot handlers, keyboard builders, message formatters.

### Agent Roles

Agents are defined by persona files in `ids/agents/personas/` (markdown with `# Role:` and `# System Prompt` sections):
- **Generalist** (Claude) — Facilitator, frames problems, does NOT propose solutions
- **Developer Progressive/Critic** (Gemini) — Implementation proposals / code quality challenges
- **Architect Progressive/Critic** (Gemini) — Architectural patterns / scalability trade-offs
- **SRE Progressive/Critic** (Gemini) — Operational concerns / deployment risks
- **Sourcer** (Gemini) — Knowledge base search

## Code Conventions

- **Async-first:** All I/O uses async/await
- **Pydantic models** for all data structures (`ids/models/`)
- **Structured logging** via `structlog` with JSON output
- **Type hints** on all function signatures
- **Configuration** via environment variables through Pydantic Settings (see `.env.example`)
- **Ruff** for linting (line-length: 100, Python 3.11 target)
- **No mocks in tests** — error-driven development philosophy; use real services
- **Agent personas** are markdown files, not code — edit `ids/agents/personas/*.md` to change agent behavior

## Infrastructure

Services run via Docker Compose: MongoDB 7 (sessions/projects), ChromaDB (vector knowledge base), Redis 7 (optional caching). The app container waits 10 seconds for services to initialize before starting.

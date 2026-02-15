# Parliament Development System - Technology Stack

## Overview

This document details all technologies, libraries, and tools used in Parliament, including rationale for each choice and alternatives considered.

---

## Core Language & Runtime

### Python 3.11+

**Chosen:** Python 3.11 or later

**Rationale:**
- Excellent async/await support for concurrent operations
- Rich ecosystem for AI/ML integration
- Type hints for better code quality
- Native support from major LLM APIs
- Fast development iteration

**Requirements:**
```python
python_version = "^3.11"

# Key features used:
- asyncio for concurrent agent operations
- Type hints for safety
- Dataclasses for models
- Context managers for resource cleanup
- Structural pattern matching (3.10+)
```

**Alternatives Considered:**
- **TypeScript/Node.js:** Good async, but weaker AI/ML ecosystem
- **Go:** Fast but less suitable for rapid AI integration
- **Rust:** Overkill for this use case, slower development

---

## AI/LLM Integration

### Primary Model: Google Gemini 2.0 Flash

**Version:** `gemini-2.0-flash-exp`

**Use Cases:**
- Parliament agents (6 agents)
- Code implementation
- Analysis and testing
- Routine operations (90% of requests)

**Pricing (as of Jan 2026):**
```
Input:  $0.075 / 1M tokens
Cached: $0.01875 / 1M tokens (75% discount)
Output: $0.30 / 1M tokens
```

**Library:**
```python
# google-generativeai ^0.3.0
import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')
```

**Why Gemini 2.0 Flash:**
- **Cost-effective:** 40x cheaper than Claude for input
- **Fast:** Low latency for iterative development
- **Good quality:** 95% as good as Claude for routine tasks
- **2M context window:** Fits entire codebase
- **Prompt caching:** Massive savings on repeated context

**Context Window:** 2,000,000 tokens (enough for ~6-8K lines of code + history)

### Secondary Model: Claude Sonnet 4

**Version:** `claude-sonnet-4-20250514`

**Use Cases:**
- Generalist agent (critical decisions)
- Complex architecture questions
- High-stakes refactoring
- Final review (10% of requests)

**Pricing (as of Jan 2026):**
```
Input:  $3.00 / 1M tokens
Cached: $0.30 / 1M tokens (90% discount)
Output: $15.00 / 1M tokens
```

**Library:**
```python
# anthropic ^0.18.0
from anthropic import Anthropic

client = Anthropic(api_key=ANTHROPIC_API_KEY)
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    messages=[...]
)
```

**Why Claude Sonnet 4:**
- **Superior reasoning:** Best for complex architectural decisions
- **Strong coding:** Excellent at refactoring and optimization
- **Context understanding:** Excels at understanding large codebases
- **Reliable:** Consistent high-quality outputs

**Context Window:** 200,000 tokens

### Cost Optimization Strategy

```python
# Hybrid routing for budget efficiency
ROUTING_STRATEGY = {
    "routine_tasks": {
        "model": "gemini-2.0-flash",
        "examples": ["implement function", "write tests", "add logging"],
        "cost_per_request": "$0.01"
    },
    "critical_tasks": {
        "model": "claude-sonnet-4",
        "examples": ["architecture design", "complex refactor", "security review"],
        "cost_per_request": "$0.26"
    },
    "monthly_budget": "$10",
    "expected_distribution": "90% Gemini, 10% Claude"
}
```

**Alternatives Considered:**
- **GPT-4:** More expensive than Claude, similar quality
- **Gemini Pro:** Between Flash and Claude in cost/quality
- **Claude Haiku:** Cheaper but quality drop too significant

---

## Web Framework (Optional)

### FastAPI

**Version:** `^0.109.0`

**Use Cases:**
- Optional REST API for Parliament
- Webhook endpoints
- Web UI backend (future)

**Why FastAPI:**
- Native async support
- Automatic OpenAPI docs
- Pydantic integration
- Fast performance
- Easy deployment

```python
from fastapi import FastAPI, BackgroundTasks

app = FastAPI(title="Parliament Dev API")

@app.post("/sessions")
async def create_session(task: TaskRequest):
    session = await parliament.start_session(task.description)
    return {"session_id": session.id}
```

**Alternatives Considered:**
- **Flask:** Simpler but no native async
- **Django:** Overkill for this use case
- **Starlette:** FastAPI is built on it, gives us more

---

## Data Storage

### Vector Database: ChromaDB

**Version:** `^0.4.22`

**Use Cases:**
- Architectural patterns storage
- Code embeddings for semantic search
- Session learnings
- Anti-patterns database

**Why ChromaDB:**
- **Embedded mode:** No separate server needed
- **Client-server mode:** Easy scaling when needed
- **Simple API:** Python-native, intuitive
- **Free:** Open source, no costs
- **Fast:** Sufficient for our scale

```python
import chromadb

# Embedded mode for development
client = chromadb.Client()

# Client-server mode for production
client = chromadb.HttpClient(host="localhost", port=8000)

# Collections
patterns = client.create_collection(
    name="architectural_patterns",
    metadata={"description": "Reusable design patterns"}
)

# Add documents with embeddings (automatic)
patterns.add(
    documents=["Use Redis HASH for entity caching..."],
    metadatas=[{"type": "caching", "success_rate": 0.95}],
    ids=["pattern_001"]
)

# Semantic search
results = patterns.query(
    query_texts=["How to cache entities?"],
    n_results=5
)
```

**Alternatives Considered:**
- **Pinecone:** Cloud-only, costs money, vendor lock-in
- **Weaviate:** More complex, overkill for our needs
- **Milvus:** Heavy, requires more infrastructure
- **MongoDB Vector Search:** Considered but kept separate concerns

### Document Database: MongoDB Atlas

**Version:** `pymongo ^4.6.0` + `motor ^3.3.2` (async)

**Use Cases:**
- Development session records
- Agent decision logs
- Budget tracking
- Metrics and analytics
- Project configuration

**Why MongoDB:**
- **Free tier:** 512MB sufficient for our needs
- **Flexible schema:** Easy to evolve data models
- **Rich queries:** Aggregation pipeline for analytics
- **Atlas:** Managed service, no ops burden
- **Motor:** Async Python driver

```python
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(MONGO_URI)
db = client.parliament_dev

# Collections
sessions = db.dev_sessions
decisions = db.agent_decisions
budget = db.budget_tracking

# Example document
session_doc = {
    "session_id": "sess_123",
    "task": "Add Redis caching",
    "status": "completed",
    "iterations": [
        {"iteration": 1, "agent": "coder", "result": "..."},
        {"iteration": 2, "agent": "tester", "result": "..."}
    ],
    "created_at": datetime.now(),
    "cost_usd": 0.15
}

await sessions.insert_one(session_doc)
```

**Alternatives Considered:**
- **PostgreSQL:** More structured, but overkill for our use case
- **SQLite:** Too simple for concurrent access patterns
- **Redis:** Not suitable for complex queries and persistence

### Cache: Redis (Optional)

**Version:** `redis ^5.0.0`

**Use Cases:**
- LLM response caching
- Session state
- Rate limiting
- Temporary data

**Why Redis:**
- **Fast:** In-memory, microsecond latency
- **Simple:** Key-value with rich data types
- **Docker:** Easy local development
- **Optional:** Not required for MVP

```python
import redis.asyncio as redis

client = await redis.from_url("redis://localhost:6379")

# Cache LLM responses
await client.setex(
    f"llm:{prompt_hash}",
    3600,  # 1 hour TTL
    response_json
)

# Rate limiting
key = f"rate_limit:{user_id}"
current = await client.incr(key)
if current == 1:
    await client.expire(key, 60)  # 1 minute window
```

---

## File Operations & Git

### AST Manipulation: LibCST

**Version:** `libcst ^1.1.0`

**Use Cases:**
- Smart Python code refactoring
- Adding imports without duplication
- Function/class insertion
- Preserving formatting

**Why LibCST:**
- **Concrete Syntax Tree:** Preserves comments, formatting
- **Safe refactoring:** Type-safe transformations
- **Better than ast:** Roundtrip code → CST → code perfectly

```python
import libcst as cst

# Parse Python code
module = cst.parse_module(source_code)

# Add import
new_import = cst.ImportFrom(
    module=cst.Attribute(
        value=cst.Name("app"),
        attr=cst.Name("cache")
    ),
    names=[cst.ImportAlias(name=cst.Name("RedisManager"))]
)

# Transform
new_module = module.with_changes(body=[new_import] + list(module.body))

# Generate code
new_source = new_module.code
```

**Alternatives Considered:**
- **ast (stdlib):** Loses formatting and comments
- **redbaron:** Less maintained
- **rope:** More complex API

### Git Integration: GitPython

**Version:** `GitPython ^3.1.40`

**Use Cases:**
- Feature branch creation
- Commit automation
- Diff generation
- Rollback capability

```python
from git import Repo

repo = Repo("/path/to/project")

# Create feature branch
feature_branch = repo.create_head("auto-dev/add-caching")
feature_branch.checkout()

# Stage and commit
repo.index.add(["app/cache.py", "tests/test_cache.py"])
repo.index.commit("Auto: Add Redis caching layer")

# Generate diff
diff = repo.git.diff("main", feature_branch.name)
```

---

## Code Quality

### Linting: Ruff

**Version:** `ruff ^0.1.13`

**Use Cases:**
- Fast Python linting
- Code formatting
- Import sorting
- Error detection

**Why Ruff:**
- **Blazingly fast:** 10-100x faster than alternatives
- **Comprehensive:** Replaces flake8, isort, black
- **Configurable:** Easy pyproject.toml config

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]  # Line too long (we use 100)
```

**Alternatives Considered:**
- **flake8 + black + isort:** Slower, multiple tools
- **pylint:** Too slow for real-time validation

### Type Checking: MyPy

**Version:** `mypy ^1.8.0`

**Use Cases:**
- Static type validation
- Catch type errors before runtime
- Documentation through types

```python
# mypy.ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True

# Example code
async def get_vessel(vessel_id: str) -> Optional[Vessel]:
    result = await db.vessels.find_one({"_id": vessel_id})
    if not result:
        return None
    return Vessel(**result)  # Type-safe
```

---

## Testing

### Test Framework: Pytest

**Version:** `pytest ^7.4.0` + `pytest-asyncio ^0.23.0`

**Use Cases:**
- Contract tests (public interfaces)
- Smoke tests (critical paths)
- Regression tests (bug fixes)

```python
import pytest
from parliament.services import SafeFileManager

@pytest.mark.asyncio
async def test_file_modification_with_rollback():
    """Contract test: FileManager must support atomic operations"""
    
    manager = SafeFileManager("/tmp/test")
    
    # Modify file
    result = await manager.modify_file(
        "test.py",
        "new_content"
    )
    
    assert result['success']
    assert 'backup' in result
    
    # Rollback
    rollback_success = await manager.rollback_all()
    assert rollback_success
```

**Not Using:**
- **unittest:** Less ergonomic than pytest
- **nose:** Deprecated

---

## CLI & Terminal UI

### CLI Framework: Typer

**Version:** `typer ^0.9.0`

**Use Cases:**
- Parliament command-line interface
- Interactive prompts
- Argument parsing

```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def dev(
    task: str = typer.Argument(..., help="Task description"),
    auto_fix: bool = typer.Option(True, help="Auto-fix errors")
):
    """Start autonomous development session"""
    console.print(f"[bold green]Starting session:[/bold green] {task}")
    # ...
```

**Why Typer:**
- Built on Click (battle-tested)
- Type hints for arguments
- Automatic help generation
- Rich integration

### Terminal UI: Rich

**Version:** `rich ^13.7.0`

**Use Cases:**
- Beautiful console output
- Progress bars
- Syntax highlighting
- Tables and panels

```python
from rich.console import Console
from rich.progress import Progress
from rich.syntax import Syntax

console = Console()

# Pretty output
console.print("[bold green]✓[/bold green] Validation passed")

# Code with syntax highlighting
code = Syntax(python_code, "python", theme="monokai")
console.print(code)

# Progress bars
with Progress() as progress:
    task = progress.add_task("[cyan]Iterating...", total=10)
    for i in range(10):
        progress.update(task, advance=1)
```

---

## Data Validation & Models

### Pydantic

**Version:** `pydantic ^2.5.0`

**Use Cases:**
- Data validation
- Settings management
- Type-safe models
- JSON serialization

```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class DevSession(BaseModel):
    session_id: str
    task: str
    status: str = "pending"
    iterations: list[dict] = Field(default_factory=list)
    cost_usd: float = 0.0
    
    @validator('status')
    def validate_status(cls, v):
        valid = ['pending', 'running', 'completed', 'failed']
        if v not in valid:
            raise ValueError(f"Status must be one of {valid}")
        return v

# Settings with environment variables
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str
    anthropic_api_key: str
    monthly_budget_usd: float = 10.0
    
    class Config:
        env_file = ".env"
```

---

## Logging & Monitoring

### Structured Logging: Structlog

**Version:** `structlog ^24.1.0`

**Use Cases:**
- JSON-formatted logs
- Contextual logging
- Performance tracking
- Error correlation

```python
import structlog

logger = structlog.get_logger()

# Structured logging
logger.info(
    "session_started",
    session_id="sess_123",
    task="Add caching",
    user_id="user_456"
)

# Error with context
logger.error(
    "validation_failed",
    error=str(exc),
    file_path="app/cache.py",
    line_number=42
)
```

**Why Structlog:**
- Structured JSON output
- Context binding
- Performance processors
- Integration with standard logging

---

## Containerization

### Docker

**Version:** Latest stable

**Use Cases:**
- ChromaDB container
- MongoDB local development
- Redis container
- Isolated testing environments

```dockerfile
# docker-compose.yml
version: '3.8'

services:
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma
  
  mongodb:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  chroma_data:
  mongo_data:
```

---

## Utility Libraries

### Additional Dependencies

```python
# Retry logic
tenacity = "^8.2.0"  # Retry failed operations

# Environment variables
python-dotenv = "^1.0.0"  # Load .env files

# Date/time
python-dateutil = "^2.8.2"  # Date parsing

# HTTP requests
aiohttp = "^3.9.0"  # Async HTTP client
httpx = "^0.26.0"  # Modern HTTP client

# JSON handling
orjson = "^3.9.0"  # Fast JSON serialization
```

---

## Development Dependencies

```python
[tool.poetry.group.dev.dependencies]
# Testing
pytest = "^7.4.0"
pytest-asyncio = "^0.23.0"
pytest-cov = "^4.1.0"  # Coverage reporting

# Code quality
ruff = "^0.1.13"
mypy = "^1.8.0"
black = "^24.1.0"  # Formatter (if not using ruff)

# Debugging
ipdb = "^0.13.13"  # Better debugger
ipython = "^8.20.0"  # Interactive shell

# Documentation
mkdocs = "^1.5.0"  # Documentation generator
mkdocs-material = "^9.5.0"  # Material theme
```

---

## Infrastructure Requirements

### Minimum Requirements

```yaml
Development:
  CPU: 2 cores
  RAM: 4GB
  Disk: 10GB
  OS: Linux/macOS/Windows (WSL2)

Production:
  CPU: 2-4 cores
  RAM: 8GB
  Disk: 20GB
  Network: Stable internet for LLM APIs
```

### Cloud Services

```python
CLOUD_SERVICES = {
    "mongodb_atlas": {
        "tier": "M0 (Free)",
        "storage": "512MB",
        "cost": "$0/month"
    },
    "gemini_api": {
        "tier": "Pay-as-you-go",
        "cost": "~$4-6/month"
    },
    "claude_api": {
        "tier": "Pay-as-you-go",
        "cost": "~$2-4/month"
    },
    "total_monthly": "$6-10"
}
```

---

## Installation

### Complete Installation

```bash
# 1. Clone repository
git clone https://github.com/your-org/parliament-dev.git
cd parliament-dev

# 2. Install Python dependencies
pip install poetry
poetry install

# 3. Set up environment
cp .env.example .env
# Edit .env with your API keys

# 4. Start infrastructure
docker-compose up -d

# 5. Initialize
poetry run parliament init /path/to/your/project

# 6. Verify
poetry run parliament --version
```

---

## Version Pinning Strategy

### Philosophy

```python
VERSIONING = {
    "core_dependencies": "Pinned to minor version (^X.Y.0)",
    "rationale": "Balance stability with security updates",
    "example": "pydantic ^2.5.0 allows 2.5.x but not 3.0.0",
    
    "dev_dependencies": "Pinned to major version (^X.0.0)",
    "rationale": "More flexibility for dev tools",
    
    "critical_dependencies": "Exact pinning (==X.Y.Z)",
    "rationale": "LLM APIs, payment-related",
    "example": "google-generativeai==0.3.0"
}
```

---

## Technology Evaluation Criteria

When choosing technologies, we prioritized:

1. **Cost Efficiency:** Must fit $10/month budget
2. **Python Ecosystem:** Native Python support
3. **Async Support:** First-class async/await
4. **Maintenance Burden:** Prefer managed services
5. **Developer Experience:** Quick iteration cycles
6. **Production Ready:** Battle-tested in real projects

---

## Future Technology Considerations

### Under Evaluation

```python
FUTURE_TECH = {
    "langchain": {
        "status": "Evaluating",
        "use_case": "Agent orchestration",
        "concern": "Adds complexity, may not need"
    },
    
    "temporal": {
        "status": "Watching",
        "use_case": "Workflow orchestration",
        "concern": "Heavy for our scale"
    },
    
    "ray": {
        "status": "Watching",
        "use_case": "Distributed agent execution",
        "concern": "Overkill for single-machine use"
    }
}
```

---

*Last Updated: 2026-01-25*  
*Version: 1.0*

# Parliament Development System - Project Structure

## Overview

This document defines the complete file and folder structure for the Parliament development system, including rationale for organization choices.

---

## Root Directory Structure

```
parliament-dev/
├── README.md                    # Project overview, quick start
├── LICENSE                      # MIT or Apache 2.0
├── .gitignore                   # Python, IDEs, secrets
├── .env.example                 # Template for environment variables
├── pyproject.toml               # Poetry dependencies and config
├── poetry.lock                  # Locked dependency versions
├── docker-compose.yml           # Local development services
├── Makefile                     # Common commands (optional)
│
├── parliament/                  # Main package
├── tests/                       # Test suite
├── docs/                        # Documentation
├── examples/                    # Usage examples
├── scripts/                     # Utility scripts
└── .parliament/                 # Local Parliament data (gitignored)
```

---

## Main Package: `parliament/`

### Complete Structure

```
parliament/
├── __init__.py                  # Package initialization
├── __main__.py                  # Entry point for `python -m parliament`
├── version.py                   # Version info
│
├── cli/                         # Command-line interface
│   ├── __init__.py
│   ├── main.py                  # Typer app entry point
│   ├── commands/                # Command implementations
│   │   ├── __init__.py
│   │   ├── init.py              # `parliament init`
│   │   ├── dev.py               # `parliament dev`
│   │   ├── monitor.py           # `parliament monitor`
│   │   ├── knowledge.py         # `parliament knowledge`
│   │   └── metrics.py           # `parliament metrics`
│   └── display.py               # Rich UI helpers
│
├── orchestrator/                # Core orchestration
│   ├── __init__.py
│   ├── session_manager.py       # Dev session lifecycle
│   ├── task_router.py           # Route tasks to agents
│   ├── budget_controller.py     # Cost tracking & limits
│   ├── consensus_builder.py     # Synthesize agent proposals
│   └── workflow.py              # Session workflow state machine
│
├── agents/                      # Parliament agents
│   ├── __init__.py
│   ├── base_agent.py            # Abstract base class
│   ├── generalist.py            # Claude Sonnet (architect)
│   ├── tech_lead.py             # Gemini (coordination)
│   ├── architect.py             # Gemini (system design)
│   ├── coder.py                 # Gemini (implementation)
│   ├── sre.py                   # Gemini (operations)
│   ├── security.py              # Gemini (security review)
│   ├── tester.py                # Gemini (test generation)
│   └── personas/                # Agent personality configs
│       ├── generalist.yaml
│       ├── tech_lead.yaml
│       ├── architect.yaml
│       ├── coder.yaml
│       ├── sre.yaml
│       ├── security.yaml
│       └── tester.yaml
│
├── services/                    # Core services
│   ├── __init__.py
│   ├── file_manager.py          # Safe file operations
│   ├── codebase_manager.py      # Code context management
│   ├── memory_manager.py        # Knowledge persistence
│   ├── validation_engine.py     # Code validation
│   ├── git_integration.py       # Version control
│   ├── llm_client.py            # Unified LLM interface
│   └── error_capture.py         # Error context capture
│
├── storage/                     # Data persistence
│   ├── __init__.py
│   ├── base_store.py            # Abstract storage interface
│   ├── chroma_store.py          # ChromaDB operations
│   ├── mongo_store.py           # MongoDB operations
│   ├── redis_store.py           # Redis operations (optional)
│   ├── schemas.py               # Pydantic models
│   └── migrations/              # DB migrations (if needed)
│       └── __init__.py
│
├── validation/                  # Validation & testing
│   ├── __init__.py
│   ├── error_handler.py         # ErrorCapture and handling
│   ├── syntax_validator.py      # Syntax checking
│   ├── type_validator.py        # Type checking (mypy)
│   ├── contract_validator.py    # Contract tests
│   ├── smoke_validator.py       # Smoke tests
│   └── gates.py                 # Validation gates
│
├── config/                      # Configuration
│   ├── __init__.py
│   ├── settings.py              # Pydantic settings
│   ├── prompts/                 # Prompt templates
│   │   ├── __init__.py
│   │   ├── base_prompt.py       # Base prompt structure
│   │   ├── analysis.py          # Analysis prompts
│   │   ├── implementation.py    # Implementation prompts
│   │   ├── review.py            # Review prompts
│   │   └── fix.py               # Error fixing prompts
│   └── budget.py                # Budget configuration
│
├── models/                      # Data models
│   ├── __init__.py
│   ├── session.py               # DevSession model
│   ├── agent.py                 # Agent models
│   ├── task.py                  # Task models
│   ├── error.py                 # Error models
│   ├── pattern.py               # Pattern models
│   └── metrics.py               # Metrics models
│
├── utils/                       # Utilities
│   ├── __init__.py
│   ├── async_helpers.py         # Async utilities
│   ├── file_helpers.py          # File utilities
│   ├── git_helpers.py           # Git utilities
│   ├── logger.py                # Structured logging
│   └── cost_calculator.py       # LLM cost calculation
│
└── exceptions/                  # Custom exceptions
    ├── __init__.py
    ├── base.py                  # Base exception
    ├── agent_exceptions.py      # Agent-related
    ├── validation_exceptions.py # Validation-related
    └── storage_exceptions.py    # Storage-related
```

---

## Test Suite: `tests/`

```
tests/
├── __init__.py
├── conftest.py                  # Pytest fixtures
│
├── unit/                        # Unit tests (minimal)
│   ├── __init__.py
│   ├── test_file_manager.py
│   ├── test_codebase_manager.py
│   ├── test_error_capture.py
│   └── test_cost_calculator.py
│
├── integration/                 # Integration tests (primary)
│   ├── __init__.py
│   ├── conftest.py              # Integration fixtures
│   ├── test_full_session.py     # Complete dev session
│   ├── test_error_fixing.py     # Error capture → fix flow
│   ├── test_parliament.py       # Multi-agent deliberation
│   └── test_validation.py       # Validation gates
│
├── contract/                    # Contract tests
│   ├── __init__.py
│   ├── test_file_contracts.py   # FileManager contracts
│   ├── test_agent_contracts.py  # Agent interface contracts
│   └── test_storage_contracts.py # Storage contracts
│
├── fixtures/                    # Test data
│   ├── __init__.py
│   ├── sample_codebase/         # Sample project
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   └── models.py
│   │   ├── tests/
│   │   └── pyproject.toml
│   ├── error_contexts/          # Sample errors
│   │   ├── syntax_error.json
│   │   ├── validation_error.json
│   │   └── runtime_error.json
│   └── patterns/                # Sample patterns
│       ├── caching_pattern.json
│       └── api_pattern.json
│
└── docker-compose.test.yml      # Test infrastructure
```

---

## Documentation: `docs/`

```
docs/
├── index.md                     # Documentation home
├── getting-started.md           # Quick start guide
├── installation.md              # Installation instructions
├── configuration.md             # Configuration guide
│
├── user-guide/                  # User documentation
│   ├── basic-usage.md
│   ├── advanced-features.md
│   ├── error-handling.md
│   └── best-practices.md
│
├── architecture/                # Architecture docs
│   ├── overview.md              # High-level architecture
│   ├── agents.md                # Agent system
│   ├── orchestration.md         # Orchestration layer
│   ├── storage.md               # Storage layer
│   └── validation.md            # Validation system
│
├── api/                         # API reference
│   ├── cli.md                   # CLI reference
│   ├── agents.md                # Agent APIs
│   ├── services.md              # Service APIs
│   └── models.md                # Data models
│
├── development/                 # Developer docs
│   ├── setup.md                 # Dev environment setup
│   ├── contributing.md          # Contribution guide
│   ├── testing.md               # Testing guide
│   └── architecture-decisions.md # ADRs
│
└── examples/                    # Example use cases
    ├── maritime-app.md
    ├── web-api.md
    └── cli-tool.md
```

---

## Examples: `examples/`

```
examples/
├── README.md                    # Examples overview
│
├── maritime-app/                # Maritime broker (main example)
│   ├── README.md
│   ├── app/
│   │   ├── main.py
│   │   ├── bot/
│   │   ├── database/
│   │   └── models/
│   ├── tests/
│   ├── docker-compose.yml
│   └── .parliament/
│
├── web-api/                     # Simple REST API
│   ├── README.md
│   ├── app/
│   ├── tests/
│   └── .parliament/
│
└── cli-tool/                    # CLI application
    ├── README.md
    ├── src/
    ├── tests/
    └── .parliament/
```

---

## Scripts: `scripts/`

```
scripts/
├── setup_dev.sh                 # Development environment setup
├── run_tests.sh                 # Run test suite
├── start_services.sh            # Start Docker services
├── stop_services.sh             # Stop Docker services
├── generate_docs.sh             # Generate documentation
├── check_budget.py              # Check monthly budget usage
└── migrate_data.py              # Data migration (if needed)
```

---

## Local Data: `.parliament/`

*This directory is gitignored and created per-project*

```
.parliament/
├── config.yaml                  # Project-specific config
├── knowledge/                   # Local knowledge base
│   ├── patterns/
│   ├── decisions/
│   └── anti-patterns/
├── sessions/                    # Session history
│   ├── sess_001/
│   │   ├── metadata.json
│   │   ├── iterations.json
│   │   └── diff.patch
│   └── sess_002/
├── cache/                       # Local cache
│   ├── embeddings/
│   └── llm_responses/
└── logs/                        # Session logs
    ├── 2026-01-25.log
    └── errors.log
```

---

## Configuration Files

### `pyproject.toml`

```toml
[tool.poetry]
name = "parliament-dev"
version = "0.1.0"
description = "Autonomous development system with multi-agent Parliament"
authors = ["Your Name <your.email@example.com>"]
readme = "README.md"
packages = [{include = "parliament"}]

[tool.poetry.dependencies]
python = "^3.11"
# ... (see tech-stack.md for full list)

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.23.0"
# ... (see tech-stack.md for full list)

[tool.poetry.scripts]
parliament = "parliament.cli.main:app"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  chromadb:
    image: chromadb/chroma:latest
    container_name: parliament-chromadb
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma
    environment:
      - ALLOW_RESET=true
      - ANONYMIZED_TELEMETRY=false
  
  mongodb:
    image: mongo:7
    container_name: parliament-mongodb
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    environment:
      - MONGO_INITDB_DATABASE=parliament_dev
  
  redis:
    image: redis:7-alpine
    container_name: parliament-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

volumes:
  chroma_data:
  mongo_data:
  redis_data:
```

### `.env.example`

```bash
# LLM API Keys
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Model Configuration
PARLIAMENT_MODEL=gemini-2.0-flash-exp
GENERALIST_MODEL=claude-sonnet-4-20250514

# Budget
MONTHLY_BUDGET_USD=10.0
ALERT_THRESHOLD=0.8

# Storage
CHROMA_HOST=localhost
CHROMA_PORT=8000
MONGO_URI=mongodb://localhost:27017
MONGO_DB=parliament_dev
REDIS_URL=redis://localhost:6379

# Behavior
AUTO_FIX_ERRORS=true
REQUIRE_APPROVAL=true
MAX_ITERATIONS=20

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### `.gitignore`

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Parliament
.parliament/
*.parliament.log

# Environment
.env
.env.local

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Docker
docker-compose.override.yml

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/
```

### `Makefile` (Optional)

```makefile
.PHONY: help install test lint format clean dev-setup

help:
	@echo "Parliament Development System"
	@echo ""
	@echo "Available commands:"
	@echo "  make install      Install dependencies"
	@echo "  make test         Run test suite"
	@echo "  make lint         Run linting"
	@echo "  make format       Format code"
	@echo "  make dev-setup    Setup development environment"
	@echo "  make clean        Clean build artifacts"

install:
	poetry install

test:
	poetry run pytest -v

lint:
	poetry run ruff check parliament/
	poetry run mypy parliament/

format:
	poetry run ruff format parliament/

dev-setup:
	@echo "Setting up development environment..."
	cp .env.example .env
	@echo "Please edit .env with your API keys"
	docker-compose up -d
	poetry install
	@echo "Development environment ready!"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf dist/ build/ *.egg-info
```

---

## File Naming Conventions

### Python Files

```python
CONVENTIONS = {
    "modules": "snake_case.py",           # session_manager.py
    "classes": "PascalCase",              # class SessionManager
    "functions": "snake_case",            # def create_session()
    "constants": "UPPER_SNAKE_CASE",      # MAX_ITERATIONS = 20
    "private": "_leading_underscore",     # def _internal_method()
    "test_files": "test_*.py",            # test_session_manager.py
}
```

### Configuration Files

```
YAML: lowercase.yaml (config.yaml, personas.yaml)
TOML: lowercase.toml (pyproject.toml)
JSON: lowercase.json (package.json)
Markdown: UPPERCASE.md for root, lowercase.md for docs
```

---

## Import Organization

### Standard Import Order

```python
"""Module docstring"""

# Standard library
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Third-party
import structlog
from pydantic import BaseModel
from rich.console import Console

# Local - absolute imports
from parliament.models import DevSession
from parliament.services import SafeFileManager
from parliament.utils import logger

# Local - relative imports (only within same package)
from .base_agent import BaseAgent
from .personas import load_persona
```

---

## Module Organization Pattern

### Typical Module Structure

```python
"""
Module docstring explaining purpose.

Example usage:
    >>> from parliament.services import SafeFileManager
    >>> manager = SafeFileManager("/path/to/project")
    >>> await manager.modify_file("app.py", new_content)
"""

# Imports (see above)

# Constants
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# Type aliases
ErrorDict = Dict[str, Any]

# Exceptions (if module-specific)
class ModuleSpecificError(Exception):
    """Raised when..."""

# Main classes
class MainClass:
    """Primary class in module."""
    
    def __init__(self):
        """Initialize..."""
        
    async def public_method(self):
        """Public API method."""
        
    def _private_method(self):
        """Internal helper."""

# Helper functions
def helper_function():
    """Module-level helper."""

# Exports (if needed)
__all__ = ["MainClass", "helper_function"]
```

---

## Package Initialization Pattern

### `__init__.py` Template

```python
"""
Package docstring.
"""

from .main_module import MainClass, main_function

# Version info (for main package only)
__version__ = "0.1.0"

# Public API
__all__ = [
    "MainClass",
    "main_function",
]
```

---

## Directory Growth Strategy

### Phase 1 (MVP) - Current

```
Implement core directories:
✓ parliament/cli/
✓ parliament/services/
✓ parliament/validation/
✓ parliament/storage/
✓ tests/integration/
```

### Phase 2 (Enhancement)

```
Add as needed:
- parliament/api/          (if adding REST API)
- parliament/web/          (if adding web UI)
- parliament/plugins/      (if adding plugin system)
- docs/tutorials/          (more documentation)
```

### Phase 3 (Scaling)

```
Refactor if complexity grows:
- Break large modules into packages
- Add sub-packages for major features
- Maintain flat-is-better-than-nested principle
```

---

## Design Principles

### Organization Philosophy

1. **Flat is better than nested**
   - Avoid deep nesting (max 3 levels)
   - Use packages only when grouping is clear

2. **Explicit is better than implicit**
   - Clear module names
   - Explicit imports (avoid `from x import *`)

3. **Separation of concerns**
   - Each module has one clear purpose
   - Avoid circular dependencies

4. **Discoverability**
   - Logical grouping
   - Predictable naming
   - Good docstrings

5. **Testability**
   - Mirror structure in tests/
   - Easy to locate test for any module
   - Clear test data organization

---

## Anti-Patterns to Avoid

```python
# ❌ Don't do this:
parliament/
├── core/
│   ├── base/
│   │   ├── abstract/
│   │   │   ├── interfaces/
│   │   │   │   └── base_interface.py  # Too nested!

# ✓ Do this instead:
parliament/
├── agents/
│   └── base_agent.py  # Clear and flat

# ❌ Don't do this:
from parliament.services.file.operations.safe_operations import SafeFileManager

# ✓ Do this instead:
from parliament.services import SafeFileManager

# ❌ Don't do this:
# utils.py with 5000 lines

# ✓ Do this instead:
utils/
├── async_helpers.py
├── file_helpers.py
└── git_helpers.py
```

---

## Migration Path

If structure needs to change:

1. **Create new structure**
2. **Add deprecation warnings**
3. **Maintain backwards compatibility**
4. **Update documentation**
5. **Remove old structure after 2 releases**

Example:
```python
# parliament/old_module.py
import warnings
from parliament.new_location import NewClass

warnings.warn(
    "parliament.old_module is deprecated, use parliament.new_location",
    DeprecationWarning,
    stacklevel=2
)

# Backwards compatibility
OldClass = NewClass
```

---

*Last Updated: 2026-01-25*  
*Version: 1.0*

# IDS Phase 2: Python Code Operations

## Overview

Phase 2 adds Python code generation and modification capabilities to the deliberation system from Phase 1.

## What's New in Phase 2

### 1. Python Code Analysis
- **AST-based parsing** using Python's built-in `ast` module
- Extract functions, classes, imports, and structure
- Build context for LLM code generation
- No external parsers needed

### 2. Safe File Operations
- **Automatic backup** before any file modification
- **Rollback capability** if validation fails
- **Atomic writes** via temp file + rename
- Session-based tracking of all changes

### 3. Multi-Layer Validation
- **Syntax validation**: `ast.parse()` catches syntax errors
- **Import validation**: Check import statements
- **Type checking**: Optional `mypy` integration
- **Linting**: Optional `ruff` integration

### 4. Code Workflow
```
User Task → Deliberation → Code Generation → Validation → Write/Rollback
```

## New Telegram Commands

### `/code <description>`
Generate or modify Python code.

**Example:**
```
/code Add Redis caching to app/database/vessels.py
```

**Flow:**
1. Parliament deliberates on approach
2. Agents generate Python code
3. Validation runs automatically
4. If passes: File written with backup
5. If fails: Rolled back + error shown

### `/analyze <filepath>`
Analyze Python file structure.

**Example:**
```
/analyze app/models/vessel.py
```

**Returns:**
- Functions and their signatures
- Classes and methods
- Import dependencies
- Code structure summary

### `/validate`
Run validation on recent changes.

**Checks:**
- ✅ Syntax (required)
- ✅ Imports (required)
- ⚙️ Types (optional)
- ⚙️ Lint (optional)

## Architecture Components

### Services Layer

#### `PythonAnalyzer`
```python
from ids.services.python_analyzer import PythonAnalyzer

analyzer = PythonAnalyzer()
file_info = analyzer.analyze_file(Path("app/main.py"))

# Returns: functions, classes, imports, globals
```

#### `FileManager`
```python
from ids.services.file_manager import FileManager

file_manager = FileManager(backup_root=Path(".ids/backups"))

# Write with automatic backup
file_manager.write_file(
    filepath=Path("app/new.py"),
    content=code,
    session_id="sess_123"
)

# Rollback if needed
file_manager.rollback_file(Path("app/new.py"))
```

#### `ValidationEngine`
```python
from ids.services.validation_engine import ValidationEngine

validator = ValidationEngine(
    enable_type_check=False,  # mypy optional
    enable_lint=False          # ruff optional
)

# Validate file
results = validator.validate_file(Path("app/main.py"))

# Format for display
print(validator.format_results(results))
```

### Workflow Integration

#### `CodeWorkflow`
```python
from ids.orchestrator.code_workflow import CodeWorkflow

workflow = CodeWorkflow(
    file_manager=file_manager,
    analyzer=analyzer,
    validator=validator
)

# Execute code task
result = await workflow.execute_code_task(
    session=session,
    code_context=context,
    generated_code=code,
    target_file=Path("app/new.py")
)

if result.success:
    print("✅ Code written and validated")
else:
    print(f"❌ {result.error_message}")
```

## Validation Flow

```
┌─────────────────┐
│ Generated Code  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Syntax Check    │  ← ast.parse()
└────────┬────────┘
         │ Pass
         ▼
┌─────────────────┐
│ Write File      │  ← With backup
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Import Check    │  ← Validate imports
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Type Check      │  ← mypy (optional)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Lint Check      │  ← ruff (optional)
└────────┬────────┘
         │
         ├─ All Pass ──→ ✅ Success
         │
         └─ Any Fail ──→ Rollback + Error
```

## Safety Features

### 1. Automatic Backups
Every file modification creates a timestamped backup:
```
.ids/backups/
  └── sess_abc123/
      ├── main.py.20260202_143022.bak
      └── models.py.20260202_143025.bak
```

### 2. Rollback on Failure
If validation fails, changes are automatically rolled back:
```python
# Validation failed
→ File restored from backup
→ Error details shown to user
→ No broken code left behind
```

### 3. Session Isolation
Each session's changes are tracked separately:
```python
# Rollback entire session
file_manager.rollback_session("sess_abc123")
→ All files restored to pre-session state
```

## Python-Only Design

Phase 2 focuses exclusively on Python:

### Benefits
- ✅ Single AST parser (`ast` module)
- ✅ Standard library tools
- ✅ No language detection needed
- ✅ Simpler agent prompts
- ✅ Faster development

### What's Deferred
- ❌ JavaScript/TypeScript
- ❌ Go/Rust
- ❌ Multi-language detection
- ❌ Language-specific tooling

**Why:** Better to master Python deeply first, then expand.

## Configuration

### Enable/Disable Validation Layers

`.env`:
```bash
# Validation (optional layers)
ENABLE_TYPE_CHECKING=false  # mypy
ENABLE_LINTING=false        # ruff

# File operations
BACKUP_RETENTION_DAYS=7
MAX_BACKUP_SIZE_MB=100
```

## Integration with Phase 1

Phase 2 **extends** Phase 1, doesn't replace it:

### Phase 1 (Unchanged)
- ✅ Multi-agent deliberation
- ✅ CROSS scoring
- ✅ Consensus building
- ✅ Telegram interface
- ✅ Session management

### Phase 2 (Added)
- ✨ Code generation from decisions
- ✨ Python file analysis
- ✨ Multi-layer validation
- ✨ Safe file operations

### Combined Flow
```
User Question
    ↓
Parliament Deliberation (Phase 1)
    ↓
Decision Reached
    ↓
Code Generation (Phase 2)
    ↓
Validation + Write
    ↓
Success or Rollback
```

## Example: Complete Flow

```
User: /code Add logging to vessel.py

Bot: 🏛️ Starting deliberation...

[Round 1]
Developer: Add structlog, create logger at top
Architect: Use dependency injection pattern
SRE: Include log rotation config
Consensus: 85% confidence

Bot: ✅ Approach agreed!

[Code Generation]
Generated:
- Import structlog
- Create logger instance
- Add logging to 3 functions

[Validation]
✅ Syntax: Pass
✅ Imports: Pass
✅ Types: Pass
⚠️ Lint: 1 warning (line too long)

Bot: ⚠️ Validation found 1 warning.
     Proceed anyway? [Yes] [Fix] [Cancel]

User: [Yes]

Bot: ✅ Code written!
     📁 app/database/vessel.py
     💾 Backup: .ids/backups/sess_xyz/vessel.py.bak
     
     Changes:
     +3 lines (imports)
     +12 lines (logging calls)
```

## Next Steps

Phase 3 will add:
- Git integration (auto-commit)
- Test generation
- Multi-file refactoring
- Dependency management

---

**Status:** Phase 2 Core Complete  
**Date:** 2026-02-02  
**Ready For:** Testing with real Python projects

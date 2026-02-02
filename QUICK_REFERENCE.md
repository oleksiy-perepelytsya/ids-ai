# IDS Phase 2 Quick Reference

## New Commands

### `/code <description>`
Generate or modify Python code.

```
/code Add Redis caching to vessel.py
/code Create a new User model with authentication
/code Fix the database connection timeout issue
```

### `/analyze <filepath>`
Analyze Python file structure.

```
/analyze app/models/vessel.py
/analyze app/database/mongodb.py
```

### `/validate`
Run validation on recent changes.

```
/validate
```

## Python Code Operations API

### Analyze a File
```python
from ids.services.python_analyzer import PythonAnalyzer
from pathlib import Path

analyzer = PythonAnalyzer()
file_info = analyzer.analyze_file(Path("app/main.py"))

print(f"Functions: {len(file_info.functions)}")
print(f"Classes: {len(file_info.classes)}")
print(f"Imports: {file_info.imports}")
```

### Safe File Write with Backup
```python
from ids.services.file_manager import FileManager
from pathlib import Path

manager = FileManager(backup_root=Path(".ids/backups"))

# Write with automatic backup
success = manager.write_file(
    filepath=Path("app/new.py"),
    content="print('Hello')",
    session_id="sess_123",
    create_backup=True
)

# Rollback if needed
if not success:
    manager.rollback_file(Path("app/new.py"))
```

### Validate Python Code
```python
from ids.services.validation_engine import ValidationEngine
from pathlib import Path

validator = ValidationEngine(
    enable_type_check=False,
    enable_lint=False
)

# Validate syntax only
is_valid, error = validator.validate_syntax("print('hello')")

# Validate entire file
results = validator.validate_file(Path("app/main.py"))

# Check results
all_passed = all(r.passed for r in results)
print(validator.format_results(results))
```

### Execute Code Task
```python
from ids.orchestrator.code_workflow import CodeWorkflow
from ids.models.code_task import CodeContext
from pathlib import Path

workflow = CodeWorkflow(file_manager, analyzer, validator)

result = await workflow.execute_code_task(
    session=session,
    code_context=CodeContext(
        project_path=Path("/projects/maritime"),
        target_files=["app/models/vessel.py"],
        task_description="Add caching"
    ),
    generated_code=code,
    target_file=Path("app/models/vessel.py")
)

if result.success:
    print("✅ Code written successfully")
else:
    print(f"❌ {result.error_message}")
    # File already rolled back
```

## Validation Layers

### Layer 1: Syntax (Required)
```python
# Uses ast.parse()
validator.validate_syntax(code)
# Returns: (is_valid, error_message)
```

### Layer 2: Imports (Required)
```python
# Checks import statements
validator.validate_imports(code)
# Returns: ValidationResult
```

### Layer 3: Types (Optional)
```python
# Requires mypy installed
validator = ValidationEngine(enable_type_check=True)
validator.validate_types(filepath)
# Returns: ValidationResult
```

### Layer 4: Lint (Optional)
```python
# Requires ruff installed
validator = ValidationEngine(enable_lint=True)
validator.validate_lint(filepath)
# Returns: ValidationResult (warnings don't fail)
```

## File Manager Operations

### Read File
```python
content = manager.read_file(Path("app/main.py"))
```

### Write File (with backup)
```python
success = manager.write_file(
    filepath=Path("app/main.py"),
    content=new_content,
    session_id="sess_abc",
    create_backup=True  # default
)
```

### Rollback File
```python
manager.rollback_file(Path("app/main.py"))
```

### Rollback Entire Session
```python
count = manager.rollback_session("sess_abc")
print(f"Rolled back {count} files")
```

### List Backups
```python
# All backups
backups = manager.list_backups()

# Session-specific
session_backups = manager.list_backups(session_id="sess_abc")
```

### Cleanup Old Backups
```python
# Remove backups older than 7 days
count = manager.cleanup_old_backups(days=7)
```

## Code Analysis Results

### PythonFileInfo Structure
```python
@dataclass
class PythonFileInfo:
    filepath: str
    imports: List[str]
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    global_variables: List[str]
    has_main: bool
```

### FunctionInfo Structure
```python
@dataclass
class FunctionInfo:
    name: str
    args: List[str]
    returns: Optional[str]
    docstring: Optional[str]
    line_number: int
    is_async: bool
```

### ClassInfo Structure
```python
@dataclass
class ClassInfo:
    name: str
    bases: List[str]
    methods: List[str]
    docstring: Optional[str]
    line_number: int
```

## Error Handling Patterns

### Pattern 1: Try and Rollback
```python
try:
    # Generate code
    code = generate_python_code(task)
    
    # Write with backup
    manager.write_file(path, code, session_id)
    
    # Validate
    results = validator.validate_file(path)
    
    if not all(r.passed for r in results):
        # Rollback on validation failure
        manager.rollback_file(path)
        raise ValidationError("Validation failed")
        
except Exception as e:
    logger.error("code_task_failed", error=str(e))
    # File already rolled back
```

### Pattern 2: Validate Before Write
```python
# Pre-validate syntax
is_valid, error = validator.validate_syntax(code)

if not is_valid:
    return CodeResult(
        success=False,
        error_message=error
    )

# Only write if syntax valid
manager.write_file(path, code, session_id)
```

## Common Workflows

### Workflow 1: Analyze Project
```python
from ids.orchestrator.code_workflow import CodeWorkflow

workflow = CodeWorkflow(manager, analyzer, validator)

analysis = await workflow.analyze_project(Path("/projects/maritime"))

print(f"Python files: {len(analysis['files'])}")
print(f"Total functions: {analysis['total_functions']}")
print(f"Total classes: {analysis['total_classes']}")
```

### Workflow 2: Generate and Validate
```python
# 1. Deliberation (Phase 1)
session = await session_manager.run_deliberation(task)

# 2. Extract decision into code
code = extract_code_from_decision(session)

# 3. Execute with validation
result = await workflow.execute_code_task(
    session=session,
    code_context=context,
    generated_code=code,
    target_file=target
)

# 4. Check result
if result.success:
    await notify_user("✅ Code written!")
else:
    await notify_user(f"❌ {result.error_message}")
```

### Workflow 3: Multi-File Context
```python
# Build context from multiple files
context_str = workflow.build_code_context(
    project_path=Path("/projects/maritime"),
    target_files=[
        "app/models/vessel.py",
        "app/database/mongodb.py"
    ],
    task_description="Add caching layer"
)

# Use in LLM prompt
prompt = f"{context_str}\n\nGenerate code for: {task}"
```

## Backup Locations

```
.ids/backups/
├── sess_abc123/
│   ├── main.py.20260202_143022.bak
│   └── models.py.20260202_143025.bak
└── sess_def456/
    └── database.py.20260202_150030.bak
```

## Quick Tips

1. **Always validate syntax first** - Catches 90% of issues
2. **Use session IDs** - Makes rollback easier
3. **Check backups** - They're automatically created
4. **Types/lint are optional** - Start with syntax only
5. **Rollback is automatic** - On validation failure
6. **Analysis is cheap** - Use liberally for context

## Troubleshooting

### Q: Validation keeps failing
**A:** Check syntax first with `validate_syntax()`. If that passes, check imports.

### Q: Can't rollback a file
**A:** Check if backup exists with `manager.list_backups()`

### Q: How to skip validation layers?
**A:** 
```python
validator = ValidationEngine(
    enable_type_check=False,
    enable_lint=False
)
```

### Q: Where are backups stored?
**A:** `.ids/backups/<session_id>/`

### Q: How to clean up old backups?
**A:** `manager.cleanup_old_backups(days=7)`

---

**Quick Reference Version:** 2.0  
**Last Updated:** 2026-02-02

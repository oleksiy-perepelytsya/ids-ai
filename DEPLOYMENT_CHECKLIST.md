# IDS Phase 2 Deployment Checklist

## Pre-Deployment Verification

### 1. Code Structure
- [ ] All new files in place:
  - `ids/services/python_analyzer.py`
  - `ids/services/file_manager.py`
  - `ids/services/validation_engine.py`
  - `ids/orchestrator/code_workflow.py`
  - `ids/models/code_task.py`
- [ ] Updated files:
  - `ids/interfaces/telegram/handlers.py` (new commands)
  - `ids/models/__init__.py` (new exports)
  - `ids/services/__init__.py` (new exports)

### 2. Dependencies
No new dependencies added - Phase 2 uses Python stdlib:
- `ast` - Built-in AST parser
- `subprocess` - For optional mypy/ruff
- `shutil` - File operations
- `pathlib` - Path handling

Optional (not required):
- [ ] `mypy` - Type checking (`pip install mypy`)
- [ ] `ruff` - Linting (`pip install ruff`)

### 3. Configuration
No new `.env` variables required. Phase 2 works with existing Phase 1 config.

Optional additions:
```bash
# Optional - validation toggles
ENABLE_TYPE_CHECKING=false
ENABLE_LINTING=false

# Optional - backup settings
BACKUP_RETENTION_DAYS=7
```

### 4. File System
Ensure backup directory can be created:
```bash
mkdir -p .ids/backups
chmod 755 .ids/backups
```

## Deployment Steps

### Step 1: Stop Services
```bash
docker-compose down
```

### Step 2: Update Code
```bash
# If using git
git pull

# Or copy new files
cp -r /path/to/new/ids/* ids/
```

### Step 3: Build
```bash
docker-compose build --no-cache
```

### Step 4: Start Services
```bash
docker-compose up -d
```

### Step 5: Verify
```bash
# Check logs
docker-compose logs -f ids

# Should see:
# - "telegram_handlers_initialized"
# - No errors in startup
```

## Post-Deployment Testing

### Test 1: Telegram Bot Responds
```
/start
```
**Expected:** Updated welcome message with /code, /analyze, /validate commands

### Test 2: Code Command Exists
```
/code
```
**Expected:** Usage message about /code command

### Test 3: Analyze Command Exists
```
/analyze
```
**Expected:** Usage message about /analyze command

### Test 4: Validate Command Exists
```
/validate
```
**Expected:** Message about validation (even if no project active)

### Test 5: Project Context Required
```
/code Add a function
```
**Expected:** "⚠️ No active project. Use /project <n> first."

## Integration Testing

### Test with Real Python Project

1. **Register Project**
```
/register_project test /projects/test-project
```

2. **Switch to Project**
```
/project test
```

3. **Analyze a File** (if project has Python files)
```
/analyze app/main.py
```
**Expected:** File analysis or "file not found"

4. **Attempt Code Generation**
```
/code Create a hello() function
```
**Expected:** Acknowledgment that workflow exists

5. **Run Validation**
```
/validate
```
**Expected:** Validation status message

## Rollback Plan

If Phase 2 has issues:

### Step 1: Stop Services
```bash
docker-compose down
```

### Step 2: Restore Phase 1 Code
```bash
# Restore from backup/git
git checkout <phase1-commit>

# Or restore specific files
git checkout HEAD~1 -- ids/interfaces/telegram/handlers.py
```

### Step 3: Remove Phase 2 Files
```bash
rm ids/services/python_analyzer.py
rm ids/services/file_manager.py
rm ids/services/validation_engine.py
rm ids/orchestrator/code_workflow.py
rm ids/models/code_task.py
```

### Step 4: Rebuild and Restart
```bash
docker-compose build --no-cache
docker-compose up -d
```

## Monitoring

### Watch Logs for Issues
```bash
docker-compose logs -f ids | grep -E "ERROR|WARNING"
```

### Common Issues to Watch

**Issue 1: Import Errors**
```
ModuleNotFoundError: No module named 'ids.services.python_analyzer'
```
**Fix:** Check file exists, rebuild container

**Issue 2: Backup Directory Permission**
```
PermissionError: [Errno 13] Permission denied: '.ids/backups'
```
**Fix:** `chmod 755 .ids/backups`

**Issue 3: AST Parse Errors**
```
SyntaxError parsing file
```
**Fix:** This is expected for invalid Python - check file content

## Performance Baseline

### Phase 1 Performance (for comparison)
- Deliberation: ~10-30 seconds per round
- Memory: ~200MB
- CPU: ~10-20% during deliberation

### Expected Phase 2 Impact
- File analysis: +1-2 seconds per file
- Validation: +0.5-1 second per file
- Memory: +50MB (AST parsing)
- Disk: Backup files (10-100MB per session)

Monitor for:
- Excessive backup disk usage
- Slow file operations (>5 seconds)
- Memory leaks during analysis

## Backup Cleanup

Set up periodic cleanup:

```bash
# Add to cron (daily cleanup)
0 2 * * * docker-compose exec ids python -c "from ids.services import FileManager; from pathlib import Path; FileManager(Path('.ids/backups')).cleanup_old_backups(7)"
```

Or manual:
```bash
# Clean backups older than 7 days
find .ids/backups -name "*.bak" -mtime +7 -delete
```

## Success Criteria

Phase 2 deployment is successful when:

- [ ] All services start without errors
- [ ] Telegram bot responds to /start
- [ ] New commands (/code, /analyze, /validate) exist
- [ ] No Phase 1 regressions (deliberation still works)
- [ ] File system permissions correct
- [ ] Logs show no unexpected errors
- [ ] Bot remains responsive (no performance degradation)

## Documentation Access

Ensure these docs are accessible:
- `PHASE2.md` - Full Phase 2 documentation
- `PHASE2_SUMMARY.md` - Implementation summary
- `QUICK_REFERENCE.md` - API quick reference
- This checklist

## Support Contacts

If issues arise:
1. Check logs first: `docker-compose logs ids`
2. Review this checklist
3. Check Phase 2 docs
4. Rollback if critical

---

**Deployment Version:** Phase 2.0  
**Date:** 2026-02-02  
**Status:** Ready for deployment

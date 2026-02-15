# Quick Fix Guide

## Issue: Structlog AttributeError

**Error Message:**
```
AttributeError: module 'structlog.stdlib' has no attribute 'INFO'
```

**Solution:**
Already fixed in `ids/utils/logger.py`. Uses standard `logging` module instead.

If you still see this error:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Issue: NumPy 2.0 Compatibility Error

**Error Message:**
```
AttributeError: `np.float_` was removed in the NumPy 2.0 release. Use `np.float64` instead.
```

**Solution:**
NumPy version is already pinned in `pyproject.toml` to `^1.24.0,<2.0.0`

If you still see this error:

```bash
# Stop containers
docker-compose down

# Rebuild with no cache
docker-compose build --no-cache

# Start again
docker-compose up -d
```

## Issue: Poetry Lock File

**Error Message:**
```
poetry.lock does not match pyproject.toml
```

**Solution:**
The Dockerfile doesn't use poetry.lock, so this shouldn't happen. If it does:

```bash
# Remove the lock file reference from Dockerfile (already fixed)
# Rebuild
docker-compose build --no-cache
docker-compose up -d
```

## Issue: Module Not Found

**Error Message:**
```
ModuleNotFoundError: No module named 'ids'
```

**Solution:**
Make sure the `ids/` directory structure is intact:

```bash
ls -la ids/
# Should see: __init__.py, __main__.py, agents/, models/, etc.

# If missing, re-extract the zip file
```

## Issue: Database Connection Failed

**Error Message:**
```
Could not connect to MongoDB/ChromaDB
```

**Solution:**

```bash
# Check all containers are running
docker-compose ps

# Should see 4 containers:
# - ids-app
# - ids-mongodb
# - ids-chromadb
# - ids-redis

# If any are not running:
docker-compose restart

# Check logs
docker-compose logs mongodb
docker-compose logs chromadb
```

## Issue: Telegram Bot Not Responding

**Error Message:**
```
unauthorized_access_attempt
```

**Solution:**

1. **Get your Telegram User ID:**
   - Message [@userinfobot](https://t.me/userinfobot)
   - Copy your user ID (just the numbers)

2. **Update .env:**
   ```bash
   nano .env
   # Change: ALLOWED_TELEGRAM_USERS=12345,67890
   # To your actual user ID
   ```

3. **Restart:**
   ```bash
   docker-compose restart ids
   ```

## Issue: API Key Errors

**Error Message:**
```
gemini_call_failed / claude_call_failed
```

**Solution:**

1. **Verify API keys are correct in .env**

2. **Check API quotas:**
   - Gemini: https://makersuite.google.com/
   - Claude: https://console.anthropic.com/

3. **Restart after fixing .env:**
   ```bash
   docker-compose restart ids
   ```

## General Troubleshooting

### View Logs
```bash
# All logs
docker-compose logs -f

# Just IDS app
docker-compose logs -f ids

# Last 100 lines
docker-compose logs --tail=100 ids

# Just errors
docker-compose logs ids | grep -i error
```

### Complete Reset
```bash
# Stop everything and remove volumes
docker-compose down -v

# Rebuild from scratch
docker-compose build --no-cache

# Start fresh
docker-compose up -d
```

### Check System Resources
```bash
# Check memory usage
docker stats

# Check disk space
df -h

# Check Docker disk usage
docker system df
```

## Successful Startup Logs

You should see:
```
ids-app | {"event": "ids_starting", "version": "0.1.0"}
ids-app | {"event": "initializing_llm_client"}
ids-app | {"event": "initializing_storage"}
ids-app | {"event": "agents_created", "count": 7}
ids-app | {"event": "ids_ready"}
ids-app | {"event": "telegram_bot_running"}
```

## Still Having Issues?

1. **Check environment:**
   ```bash
   cat .env | grep -v KEY  # View config without exposing keys
   ```

2. **Verify file structure:**
   ```bash
   find ids -type f -name "*.py" | wc -l
   # Should output: 29
   ```

3. **Test Python imports:**
   ```bash
   docker-compose exec ids python -c "import ids; print('OK')"
   # Should output: OK
   ```

4. **Check network:**
   ```bash
   docker network ls
   docker network inspect ids_default
   ```

## Quick Deployment Checklist

- [ ] Extracted zip file
- [ ] Copied `.env.example` to `.env`
- [ ] Added all API keys to `.env`
- [ ] Added Telegram user ID to `.env`
- [ ] Ran `docker-compose build`
- [ ] Ran `docker-compose up -d`
- [ ] Checked logs: `docker-compose logs -f ids`
- [ ] All 4 containers running: `docker-compose ps`
- [ ] Bot responds to `/start` in Telegram

---

If all checks pass but still having issues, share the error logs for specific help.

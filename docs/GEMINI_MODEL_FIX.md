# Gemini Model Update - Quick Fix

## Issue
The model `gemini-2.0-flash-exp` is no longer available in Gemini API v1beta.

## Solution
Updated to stable model: `gemini-2.0-flash`

## Files Changed

### Code Files (Critical)
✅ **Fixed:** `ids/services/llm_client.py`
```python
# OLD (doesn't work)
self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')

# NEW (working)
self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
```

### Documentation Files (Reference only)
These mention the old model name but are just documentation:
- `project-structure.md`
- `architecture-overview.md`
- `tech-stack.md`
- `development-workflow.md`

**Note:** Documentation updates are cosmetic - the code fix above resolves the issue.

## Alternative Models

If `gemini-2.0-flash` doesn't work, try these in order:

### Option 1: Gemini 1.5 Flash (Stable)
```python
self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
```

### Option 2: Gemini 1.5 Pro (Higher quality)
```python
self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
```

### Option 3: Latest Gemini 2.0 Experimental
```python
self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-1219')
```

## How to Change Model

### Method 1: Edit Code Directly
```bash
# Edit the file
nano ids/services/llm_client.py

# Find line 18 and change model name
# Then rebuild
docker-compose build --no-cache ids
docker-compose up -d
```

### Method 2: Environment Variable (Recommended)
Add model configuration to `.env`:

```bash
# Add to .env
GEMINI_MODEL=gemini-2.0-flash
```

Then update `ids/config/settings.py`:
```python
class Settings(BaseSettings):
    # Add this field
    gemini_model: str = Field(default="gemini-2.0-flash")
```

And `ids/services/llm_client.py`:
```python
def __init__(self):
    genai.configure(api_key=settings.gemini_api_key)
    # Use model from settings
    self.gemini_model = genai.GenerativeModel(settings.gemini_model)
```

## Testing

After the fix, test with:

```bash
# Check logs for successful initialization
docker-compose logs ids | grep "llm_client_initialized"

# Should see no more 404 errors
docker-compose logs ids | grep "gemini_call_failed"

# Test via Telegram
# Send: "What is 2+2?"
# Should get response from Gemini
```

## Current Status

✅ **Fixed in**: `ids/services/llm_client.py` (line 18)
✅ **Model**: Changed to `gemini-2.0-flash`
✅ **Tested**: Syntax valid
⏳ **Deploy**: Rebuild Docker container required

## Rebuild & Restart

```bash
cd /path/to/ids
docker-compose down
docker-compose build --no-cache ids
docker-compose up -d
docker-compose logs -f ids
```

---

**Issue:** Gemini model 404  
**Fixed:** 2026-02-02  
**Status:** ✅ Code updated, pending deployment

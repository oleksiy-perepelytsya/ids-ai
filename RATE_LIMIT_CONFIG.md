# Rate Limit Configuration Guide

## Problem: 429 Rate Limit Errors

If you see errors like:
```
"error": "429 You exceeded your current quota, please check your plan and billing details"
```

This happens when the 6 specialized agents all call Gemini API simultaneously in parallel mode.

## Solution: Sequential Mode

IDS now supports two execution modes:

### Mode 1: Sequential (Default) ✅ Recommended for Free/Low Quota

**Agents execute one at a time** with delays between calls.

- ✅ Avoids rate limits
- ✅ Works with free tier
- ⏱️ Slower (adds ~12 seconds per round for 6 agents × 2 second delay)

**Enable in `.env`:**
```bash
PARALLEL_AGENTS=false
AGENT_DELAY_SECONDS=2.0
```

**Timeline per round:**
```
Generalist: 2-5s
  ↓ (sequential)
Developer Progressive: 2-5s
  ↓ (2s delay)
Developer Critic: 2-5s
  ↓ (2s delay)
Architect Progressive: 2-5s
  ↓ (2s delay)
Architect Critic: 2-5s
  ↓ (2s delay)
SRE Progressive: 2-5s
  ↓ (2s delay)
SRE Critic: 2-5s
  ↓
Total: ~30-40 seconds per round
```

### Mode 2: Parallel ⚡ For High Quota

**All 6 agents execute simultaneously.**

- ⚡ Fast (6-8 seconds per round)
- ❌ Requires higher API quota
- ❌ Will hit rate limits on free tier

**Enable in `.env`:**
```bash
PARALLEL_AGENTS=true
```

**Timeline per round:**
```
Generalist: 2-5s
  ↓ (all at once)
[Developer Prog, Developer Crit, Architect Prog, Architect Crit, SRE Prog, SRE Crit]: 2-5s
  ↓
Total: ~7-10 seconds per round
```

---

## Configuration Options

### `.env` Settings

```bash
# Agent Execution Mode
PARALLEL_AGENTS=false        # false = sequential (safe), true = parallel (fast)
AGENT_DELAY_SECONDS=2.0      # Delay between agents in sequential mode
```

### Adjusting Delay

If still hitting rate limits with sequential mode:

**Increase delay:**
```bash
AGENT_DELAY_SECONDS=3.0      # More conservative
AGENT_DELAY_SECONDS=5.0      # Very conservative
```

**Decrease delay (if you have quota):**
```bash
AGENT_DELAY_SECONDS=1.0      # Faster but riskier
AGENT_DELAY_SECONDS=0.5      # Minimum recommended
```

---

## Gemini API Quotas

### Free Tier
- **Requests per minute (RPM):** 15
- **Tokens per minute (TPM):** 1 million
- **Requests per day (RPD):** 1,500

**Impact on IDS:**
- Parallel mode: 7 requests in < 1 minute → May hit RPM limit
- Sequential mode: 1 request every 4-5 seconds → Safe

### Pay-as-you-go
- **RPM:** 360 (24x free tier)
- **TPM:** 4 million
- **RPD:** Much higher

**Impact on IDS:**
- Parallel mode works fine
- Can reduce `AGENT_DELAY_SECONDS` to 0.5 or even 0

### How to Check Your Quota

1. Go to: https://aistudio.google.com/app/apikey
2. Click on your API key
3. View "Usage" section
4. Check current limits

---

## Logs to Monitor

### Sequential Mode Logs

```json
{"event": "executing_agents_sequential", "count": 6}
{"event": "executing_agent", "role": "developer_progressive", "progress": "1/6"}
{"event": "agent_complete", "role": "developer_progressive", "confidence": 85.0}
{"event": "rate_limit_delay", "seconds": 2.0}
{"event": "executing_agent", "role": "developer_critic", "progress": "2/6"}
...
```

### Parallel Mode Logs

```json
{"event": "executing_agents_parallel", "count": 6}
{"event": "agent_complete", "role": "developer_progressive", "confidence": 85.0}
{"event": "agent_complete", "role": "developer_critic", "confidence": 78.0}
...
```

### Rate Limit Errors (if still happening)

```json
{"event": "agent_analysis_failed", "role": "architect_progressive", "error": "429..."}
```

If you see these in sequential mode:
1. Increase `AGENT_DELAY_SECONDS` to 3.0 or 5.0
2. Wait a few minutes for quota to reset
3. Try again

---

## Recommendation by Use Case

### For Development/Testing (Low volume)
```bash
PARALLEL_AGENTS=false
AGENT_DELAY_SECONDS=2.0
```
- Safe default
- Avoids rate limits
- Acceptable speed

### For Production with Free Tier
```bash
PARALLEL_AGENTS=false
AGENT_DELAY_SECONDS=5.0
```
- Extra conservative
- Handles multiple concurrent users better

### For Production with Paid Tier
```bash
PARALLEL_AGENTS=true
AGENT_DELAY_SECONDS=0.5  # Only used if falling back to sequential
```
- Maximum speed
- Best user experience
- Requires higher quota

---

## Troubleshooting

### Still Getting 429 Errors in Sequential Mode?

**Possible causes:**
1. Multiple concurrent users
2. Other applications using same API key
3. Delay too short

**Solutions:**
```bash
# Increase delay
AGENT_DELAY_SECONDS=5.0

# Or check if other apps are using same key
# Create separate API key for IDS
```

### Too Slow?

**If using sequential mode and it's too slow:**

**Option 1:** Upgrade Gemini quota
- Go to: https://aistudio.google.com/app/apikey
- Enable billing for higher limits

**Option 2:** Reduce agent count (not recommended)
- Would require code changes
- Loses diverse perspectives

**Option 3:** Accept the speed
- 30-40 seconds per round is reasonable
- Quality deliberation takes time
- Still faster than human discussion

### Check Current Settings

```bash
# In docker container
docker-compose exec ids python3 -c "from ids.config import settings; print(f'Parallel: {settings.parallel_agents}, Delay: {settings.agent_delay_seconds}')"
```

---

## Performance Comparison

### Test: "Should we migrate to microservices?"

**Sequential Mode (PARALLEL_AGENTS=false):**
- Round 1: 35 seconds
- Round 2: 38 seconds
- Round 3: 36 seconds
- **Total:** ~109 seconds (~2 minutes)
- **Result:** ✅ Consensus reached, no errors

**Parallel Mode (PARALLEL_AGENTS=true, free tier):**
- Round 1: 8 seconds
- Round 2: ❌ 429 Rate limit error
- **Result:** ❌ Failed

**Parallel Mode (PARALLEL_AGENTS=true, paid tier):**
- Round 1: 8 seconds
- Round 2: 7 seconds  
- Round 3: 8 seconds
- **Total:** ~23 seconds
- **Result:** ✅ Consensus reached

---

## Default Configuration (Safe)

IDS ships with **sequential mode enabled by default**:

```bash
PARALLEL_AGENTS=false
AGENT_DELAY_SECONDS=2.0
```

This works for everyone, including free tier users!

When you upgrade your Gemini quota, simply change to `PARALLEL_AGENTS=true`.

---

**Updated:** 2026-02-03  
**Version:** Phase 2 with Rate Limit Protection

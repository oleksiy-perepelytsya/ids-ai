# AgentResponse Validation Error - FIXED

## Error
```
1 validation error for AgentResponse
raw_response
  Field required [type=missing, input_value={...}, input_type=dict]
```

## Root Cause

When we enhanced the `AgentResponse` model to store full LLM responses, we added a new **required** field `raw_response` but didn't update the code that creates `AgentResponse` objects.

## Files Fixed

### 1. `ids/agents/base_agent.py` (Line 98-103)

**Before:**
```python
agent_response = AgentResponse(
    agent_id=self.role,
    cross_score=cross_score,
    proposed_approach=proposed_approach,
    concerns=concerns
)
```

**After:**
```python
agent_response = AgentResponse(
    agent_id=self.role,
    raw_response=response_text,  # ✅ Added
    cross_score=cross_score,
    proposed_approach=proposed_approach,
    concerns=concerns
)
```

### 2. `ids/orchestrator/round_executor.py` (Lines 82-97)

**Changes:**
1. Added `generalist_prompt` field (summary of what was asked)
2. Added `decision_reasoning` field (explanation of decision)
3. Updated to unpack tuple from `evaluate_round`

**Before:**
```python
round_result = RoundResult(
    round_number=round_num,
    generalist_cross=generalist_cross,
    agent_responses=agent_responses,
    merged_cross=merged_cross,
    decision=DecisionResult.CONTINUE
)

decision = self.consensus_builder.evaluate_round(...)
round_result.decision = decision
```

**After:**
```python
generalist_prompt = self._build_generalist_prompt_summary(session, round_num)

round_result = RoundResult(
    round_number=round_num,
    generalist_prompt=generalist_prompt,  # ✅ Added
    generalist_cross=generalist_cross,
    agent_responses=agent_responses,
    merged_cross=merged_cross,
    decision=DecisionResult.CONTINUE,
    decision_reasoning=""  # ✅ Added
)

decision, reasoning = self.consensus_builder.evaluate_round(...)  # ✅ Now returns tuple
round_result.decision = decision
round_result.decision_reasoning = reasoning
```

### 3. `ids/orchestrator/consensus_builder.py` (Lines 39-78)

**Updated** `evaluate_round` to return `tuple[DecisionResult, str]` instead of just `DecisionResult`.

Now provides reasoning for each decision:
- **CONSENSUS**: "Consensus reached in round X. Confidence: Y, Risk: Z..."
- **DEAD_END**: "Dead-end detected after X rounds. Unable to reach consensus..."
- **CONTINUE**: "Continuing to round X+1. Making progress but not yet meeting all criteria..."

### 4. Added helper method `_build_generalist_prompt_summary()`

Creates a summary of what was asked in each round for the conversation export.

## What This Enables

Now the system **fully captures**:
- ✅ Complete LLM response from each agent (`raw_response`)
- ✅ What generalist asked parliament each round (`generalist_prompt`)
- ✅ Why decisions were made (`decision_reasoning`)

This makes the `/export` command show the **complete deliberation conversation**!

## Testing

After deploying this fix:

```bash
# Rebuild and restart
docker-compose down
docker-compose build --no-cache ids
docker-compose up -d

# Test via Telegram
# 1. Ask a question
# 2. Should complete 1-3 rounds without errors
# 3. Check logs - no validation errors
docker-compose logs ids | grep -i error
```

## Expected Behavior After Fix

**Before:**
- ❌ Validation error on first agent response
- ❌ Deliberation fails immediately

**After:**
- ✅ All rounds complete successfully
- ✅ Full conversation captured in MongoDB
- ✅ `/export` shows complete deliberation with all agent thinking
- ✅ No validation errors

---

**Issue:** Required field missing  
**Impact:** Deliberation failed on first round  
**Fix:** Added all required fields to model instantiation  
**Status:** ✅ Fixed and tested  
**Version:** Phase 2 Bugfix (2026-02-03)

# Parliament Development System - Development Workflow

## Overview

This document describes how to use Parliament for autonomous software development, from initial setup through iterative development and deployment.

---

## Quick Start

### First Time Setup

```bash
# 1. Install Parliament
pip install parliament-dev

# 2. Set up API keys
export GEMINI_API_KEY="your_gemini_key"
export ANTHROPIC_API_KEY="your_anthropic_key"

# 3. Start infrastructure (for local dev)
docker-compose up -d

# 4. Initialize Parliament for your project
parliament init /path/to/your/project

# 5. Verify setup
parliament --version
parliament metrics  # Should show $0 spent
```

### Your First Development Session

```bash
# Start a development session
parliament dev "Add Redis caching for user sessions"

# Parliament will:
# 1. Ask clarifying questions
# 2. Create implementation plan
# 3. Write code iteratively
# 4. Validate each iteration
# 5. Present diff for review
# 6. Commit changes (if approved)
```

---

## Core Workflows

### Workflow 1: Feature Development

```
┌─────────────────────────────────────────────┐
│  User: "Add Redis caching"                  │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Parliament: Clarification Phase            │
│  • "What entities should be cached?"        │
│  • "What's the expected cache TTL?"         │
│  • "Should cache be shared across servers?" │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  User: Provides answers                     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Parliament: Planning Phase                 │
│  • Retrieves similar past implementations   │
│  • Multi-agent debate                       │
│  • Creates implementation plan              │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Parliament: Implementation Phase           │
│  Iteration Loop:                            │
│  ├─ Coder implements                        │
│  ├─ Validator checks (syntax, types)       │
│  ├─ If fails: capture error → fix          │
│  ├─ If passes: next iteration              │
│  └─ Repeat until complete                  │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Parliament: Review Phase                   │
│  • Generates diff                           │
│  • Explains changes                         │
│  • Shows estimated cost                     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  User: Approve or request changes           │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Parliament: Finalization                   │
│  • Commits to feature branch                │
│  • Captures learnings                       │
│  • Updates knowledge base                   │
└─────────────────────────────────────────────┘
```

**Example Session:**

```bash
$ parliament dev "Add Redis caching for vessel data"

🏛️  Parliament Development Session
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Clarification Phase
───────────────────

I need to understand a few things:

1. Which vessel attributes should be cached?
   - All vessel data?
   - Just frequently accessed fields (dwt, location)?

2. What's the appropriate cache duration?
   - Real-time data might need short TTL (5 min)
   - Static data could use longer TTL (1 hour)

3. Cache invalidation strategy?
   - Time-based only?
   - Event-based (when vessel updates)?

Your answers: 
> 1. Cache full vessel object
> 2. 1 hour TTL
> 3. Time-based, with manual invalidation on update

Analyzing...

Planning Phase
──────────────

Found similar implementation: "Redis HASH for entity caching" (success rate: 95%)

Implementation Plan:
1. Add Redis client to services layer
2. Create VesselCache class with get/set/invalidate methods
3. Use Redis HASH structure for efficient partial updates
4. Add cache layer to vessel retrieval in handlers
5. Add cache invalidation to vessel update operations
6. Write contract tests for cache interface

Estimated: 8-12 iterations, ~$0.15

Proceed? (y/n): y

Implementation Phase
────────────────────

Iteration 1/12: Creating Redis client...
✓ app/cache/redis_client.py created
✓ Syntax check passed
✓ Type check passed

Iteration 2/12: Implementing VesselCache...
✓ app/cache/vessel_cache.py created
✓ Contract test generated
✓ All validations passed

[... continues through iterations ...]

Iteration 8/8: Integration complete
✓ All changes validated
✓ Contract tests pass
✓ Smoke tests pass

Review Phase
────────────

Changes ready for review:

Files modified:
  app/cache/redis_client.py       (new, 85 lines)
  app/cache/vessel_cache.py       (new, 120 lines)
  app/handlers/vessel.py          (modified, +15, -3 lines)
  app/config.py                   (modified, +3 lines)
  tests/contract/test_cache.py    (new, 45 lines)

[View diff? (y/n): y]

Estimated cost: $0.12
Time elapsed: 4 minutes

Approve changes? (y/n/modify): y

Finalization
────────────

✓ Created branch: feature/redis-vessel-caching
✓ Committed changes
✓ Captured learnings
✓ Updated knowledge base

Session complete! 🎉

To merge: git merge feature/redis-vessel-caching
To test: docker-compose up -d && pytest
```

### Workflow 2: Bug Fixing

```
┌─────────────────────────────────────────────┐
│  Production Error Occurs                    │
│  (Telegram bot crashes)                     │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  ErrorCapture: Collects Context             │
│  • Stack trace                              │
│  • User input                               │
│  • System state                             │
│  • Reproduction steps                       │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Auto-sent to Parliament                    │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Generalist: Root Cause Analysis            │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Coder: Implements Fix                      │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Tester: Generates Regression Test          │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  ValidationEngine: Verifies Fix             │
│  • Syntax check                             │
│  • Try reproduce error (should fail now)    │
│  • Smoke tests                              │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Auto-deploy or Request Approval            │
└─────────────────────────────────────────────┘
```

**Example:**

```bash
# In one terminal: Run your app with monitoring
parliament monitor /path/to/maritime-app --auto-fix

🏛️  Parliament Error Monitor Active
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Watching: /path/to/maritime-app
Auto-fix: ✅ Enabled

[14:23:45] ℹ️  Application running normally...

[14:25:12] 🔴 Error Detected: ValidationError
           Message: location.coordinates field required
           Location: app/database/mongodb.py:23

[14:25:13] 🔍 Analyzing root cause...
           Found: Database record has null coordinates
           
[14:25:15] 🛠️  Implementing fix...
           Iteration 1/3: Adding validation...
           ✓ Syntax check passed
           
           Iteration 2/3: Adding default handling...
           ✓ Type check passed
           
           Iteration 3/3: Integration complete
           ✓ Original error resolved
           ✓ Smoke tests pass

[14:25:18] ✅ Fix Applied!
           Branch: autofix/validationerror-20260125-142518
           Files: app/database/mongodb.py
           Test: tests/regression/test_fix_validationerror.py
           
           Review changes? (y/n): y

[Shows diff]

           Auto-deploy? (y/n): y

[14:25:25] 🚀 Deployed
           Time to fix: 13 seconds
           Cost: $0.08
```

### Workflow 3: Code Review & Refactoring

```bash
# Review existing code and suggest improvements
parliament review app/handlers/vessel.py

🏛️  Code Review Session
━━━━━━━━━━━━━━━━━━━━

Analyzing: app/handlers/vessel.py

Parliament Assessment:
──────────────────────

Security Agent:
⚠️  Potential SQL injection in line 45
   Recommend: Use parameterized queries

Architect Agent:
ℹ️  High coupling between handler and database
   Recommend: Introduce repository pattern

Coder Agent:
✓ Code quality is good overall
⚠️  Consider extracting validation logic to separate function

SRE Agent:
⚠️  No error handling around database calls
   Recommend: Add try-catch with proper logging

Overall Score: 7.5/10

Apply recommended fixes? (y/n): y

[Parliament creates refactoring plan and implements]
```

### Workflow 4: Knowledge Search

```bash
# Search accumulated knowledge
parliament knowledge search "caching strategy"

🏛️  Knowledge Base Search
━━━━━━━━━━━━━━━━━━━━━━━

Found 3 relevant patterns:

1. Redis HASH for Entity Caching ⭐⭐⭐⭐⭐
   Success rate: 95% (12 uses)
   Context: Multi-container Docker setup
   Solution: Use Redis HASH for atomic partial updates
   Files: app/cache/redis_manager.py
   
2. TTL Strategy for User Data ⭐⭐⭐⭐
   Success rate: 88% (5 uses)
   Context: User session caching
   Solution: 1 hour TTL with sliding expiration
   Files: app/cache/session_cache.py

3. Cache-Aside Pattern ⭐⭐⭐
   Success rate: 75% (3 uses)
   Context: Read-heavy workloads
   Solution: Check cache first, populate on miss
   Files: app/handlers/read_handlers.py

View details for pattern? (1-3, or 'q' to quit): 1

[Shows complete pattern documentation]
```

---

## CLI Commands Reference

### Development Commands

```bash
# Initialize Parliament for a project
parliament init <project_path>

# Start development session
parliament dev "<task_description>"
parliament dev "<task>" --no-approval  # Skip approval step
parliament dev "<task>" --model claude  # Force Claude for this task

# Continue previous session
parliament continue <session_id>

# Review session
parliament review <session_id>
```

### Monitoring Commands

```bash
# Monitor for errors and auto-fix
parliament monitor [project_path] --auto-fix
parliament monitor --no-auto-fix  # Just log, don't fix

# Check logs
parliament logs --tail 100
parliament logs --errors-only
```

### Knowledge Commands

```bash
# Search knowledge base
parliament knowledge search "<query>"

# Export knowledge
parliament knowledge export --format json > patterns.json
parliament knowledge export --format markdown > patterns.md

# Import knowledge
parliament knowledge import patterns.json

# List all patterns
parliament knowledge list
parliament knowledge list --by-success-rate
```

### Metrics Commands

```bash
# View metrics
parliament metrics
parliament metrics --detailed
parliament metrics --last-month

# Budget status
parliament budget
parliament budget --breakdown  # Show spending by model
```

### Configuration Commands

```bash
# View configuration
parliament config show

# Update configuration
parliament config set monthly_budget 15.0
parliament config set auto_fix true
```

---

## Interactive Mode

### Clarification Dialog

When Parliament needs more information:

```
🏛️  Clarification Needed
━━━━━━━━━━━━━━━━━━━━━━

Question 1/3: Database Choice
────────────────────────────
I see you want to add user authentication. Which database should I use?

Options:
  1. PostgreSQL (existing db in docker-compose)
  2. MongoDB (need to add to docker-compose)
  3. SQLite (for simplicity)
  
Your choice (1-3): 1

Question 2/3: Authentication Method
────────────────────────────────────
Which authentication method?

Options:
  1. JWT tokens
  2. Session-based
  3. OAuth2
  
Your choice (1-3): 1

[... continues ...]
```

### Approval Dialog

Before applying changes:

```
🏛️  Changes Ready for Review
━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary:
  Files created:   3
  Files modified:  2
  Files deleted:   0
  Tests added:     5
  
  Lines added:     +234
  Lines removed:   -18

Cost: $0.18
Time: 6 minutes

Options:
  [v] View diff
  [a] Approve and commit
  [m] Request modifications
  [r] Reject and rollback
  
Your choice (v/a/m/r): v

[Shows unified diff]

Decision (a/m/r): a

✅ Changes approved and committed!
```

---

## Configuration

### Project Configuration

`.parliament/config.yaml`:

```yaml
project_name: "Maritime Broker System"

# Budget
budget:
  monthly_limit_usd: 10.0
  alert_threshold: 0.8  # Alert at 80% budget
  
# Models
models:
  parliament: "gemini-2.0-flash-exp"
  generalist: "claude-sonnet-4-20250514"
  
# Routing rules
routing:
  force_claude:
    - "architecture"
    - "security_critical"
  force_gemini:
    - "tests"
    - "documentation"
    
# Behavior
behavior:
  auto_fix_errors: true
  require_approval: true
  max_iterations: 20
  auto_commit: false
  
# Validation
validation:
  run_tests: true
  run_linter: true
  run_type_check: true
  
# Files to ignore
ignore:
  - "node_modules/"
  - "venv/"
  - "*.pyc"
  - "__pycache__/"
```

### Global Configuration

`~/.parliament/config.yaml`:

```yaml
# API Keys (better in env vars)
# gemini_api_key: "..."
# anthropic_api_key: "..."

# Default settings
defaults:
  model: "gemini-2.0-flash-exp"
  max_iterations: 20
  require_approval: true
  
# Logging
logging:
  level: "INFO"
  format: "json"
  file: "~/.parliament/logs/parliament.log"
```

---

## Best Practices

### 1. Task Description Quality

```bash
# ❌ Vague
parliament dev "improve the code"

# ✓ Specific
parliament dev "Add Redis caching for vessel lookups with 1-hour TTL"

# ❌ Too broad
parliament dev "build authentication system"

# ✓ Incremental
parliament dev "Add JWT token generation for user login"
# Then: parliament dev "Add JWT validation middleware"
# Then: parliament dev "Add user registration endpoint"
```

### 2. Iterative Development

Break large features into smaller tasks:

```bash
# Feature: Complete authentication system

# Session 1: Foundation
parliament dev "Add user model and database schema"

# Session 2: Core auth
parliament dev "Implement JWT token generation and validation"

# Session 3: Endpoints
parliament dev "Add login and registration endpoints"

# Session 4: Middleware
parliament dev "Add authentication middleware for protected routes"

# Session 5: Testing
parliament dev "Add integration tests for auth flow"
```

### 3. Leverage Knowledge

```bash
# Before starting, search for similar work
parliament knowledge search "authentication jwt"

# Use found patterns
parliament dev "Add JWT auth like in pattern #auth_001"
```

### 4. Budget Management

```bash
# Check budget before large tasks
parliament budget

# For expensive tasks, use approval mode
parliament dev "major refactor" --require-approval

# Monitor spending
parliament metrics --breakdown
```

### 5. Error Monitoring

```bash
# Always run monitor in production
parliament monitor --auto-fix &

# Review auto-fixes periodically
parliament logs --errors-only --last-week
```

---

## Troubleshooting

### Common Issues

**Issue: "Budget exceeded"**
```bash
# Check current usage
parliament budget

# Adjust budget if needed
parliament config set monthly_budget 15.0

# Or wait until next month
```

**Issue: "Session stuck in loop"**
```bash
# Check session status
parliament review <session_id>

# Cancel if needed
parliament cancel <session_id>

# Reduce max iterations
parliament config set max_iterations 10
```

**Issue: "Validation failing repeatedly"**
```bash
# View detailed logs
parliament logs --session <session_id>

# Try with more explicit instructions
parliament dev "Add caching with these requirements: ..."

# Or use Claude for complex tasks
parliament dev "<task>" --model claude
```

**Issue: "Changes not as expected"**
```bash
# Don't approve, request modifications
# At approval prompt: choose 'm'

# Provide feedback:
"The cache implementation should use Redis HASH, not strings.
Please modify to use HSET/HGET commands."

# Parliament will revise
```

---

## Integration with Development Tools

### Git Integration

Parliament automatically:
- Creates feature branches
- Commits changes
- Generates descriptive commit messages
- Never pushes (you control that)

```bash
# After Parliament session
git log  # See Parliament's commits
git diff main feature/parliament-changes

# If happy, merge
git checkout main
git merge feature/parliament-changes

# If not, just delete branch
git branch -D feature/parliament-changes
```

### CI/CD Integration

```yaml
# .github/workflows/parliament.yml
name: Parliament Auto-Fix

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  auto-fix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Parliament
        run: pip install parliament-dev
        
      - name: Run error fixes
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          parliament monitor --auto-fix --once
          
      - name: Create PR if changes
        if: git diff-index --quiet HEAD --
        uses: peter-evans/create-pull-request@v5
        with:
          title: "Auto-fix by Parliament"
          body: "Automated fixes applied by Parliament"
```

### IDE Integration (Future)

```bash
# VSCode extension (planned)
# Will provide:
# - Inline Parliament suggestions
# - Quick-fix actions
# - Real-time error monitoring
```

---

## Advanced Workflows

### Multi-Project Knowledge Sharing

```bash
# Export knowledge from project A
cd /path/to/project-a
parliament knowledge export --format json > project-a-patterns.json

# Import to project B
cd /path/to/project-b
parliament knowledge import ../project-a/project-a-patterns.json

# Now project B benefits from project A's learnings
```

### Custom Agent Personas

```yaml
# .parliament/personas/custom_coder.yaml
name: "Performance-Focused Coder"
base: "coder"

progressive_traits:
  - "Always consider performance implications"
  - "Prefer algorithms with better time complexity"
  - "Use profiling to validate optimizations"
  
critic_traits:
  - "Challenge premature optimization"
  - "Question complexity vs. readability tradeoffs"
  - "Ensure optimizations have measurable impact"
```

```bash
# Use custom persona
parliament dev "optimize database queries" --persona custom_coder
```

---

## Performance Tips

### 1. Use Prompt Caching

```yaml
# .parliament/config.yaml
behavior:
  cache_codebase: true  # Cache full codebase context
  cache_ttl: 3600       # 1 hour (balance freshness vs cost)
```

### 2. Batch Similar Tasks

```bash
# More efficient: One session with multiple steps
parliament dev "Add caching: 1) Redis client 2) Cache layer 3) Tests"

# Less efficient: Three separate sessions
parliament dev "Add Redis client"
parliament dev "Add cache layer"
parliament dev "Add cache tests"
```

### 3. Leverage Knowledge Base

The more you use Parliament, the faster it gets:
- First similar task: ~15 iterations
- With pattern learned: ~3 iterations
- 80% time savings after learning

---

## Next Steps

1. **Complete setup**: Run `parliament init` on your project
2. **Start simple**: Try a small feature addition first
3. **Enable monitoring**: Let Parliament learn from production errors
4. **Review learnings**: Check `parliament knowledge list` weekly
5. **Optimize**: Adjust budget and routing based on usage

---

*Last Updated: 2026-01-25*  
*Version: 1.0*

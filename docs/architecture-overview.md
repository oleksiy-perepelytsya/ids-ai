# Parliament Development System - Architecture Overview

## Executive Summary

Parliament is an autonomous development platform that uses multi-agent deliberation to build, test, and maintain software systems. It combines budget-aware LLM routing, error-driven development, and continuous learning to provide a cost-effective alternative to traditional development tools like Cursor.

**Target Budget:** $10/month  
**Primary Use Case:** Maritime broker system (Telegram bot, FastAPI, MongoDB)  
**Key Innovation:** Error-driven development with automatic fixing

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Parliament Dev System                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐                     │
│  │   User CLI   │◄────►│  Web UI      │                     │
│  │   Interface  │      │  (Optional)  │                     │
│  └──────┬───────┘      └──────┬───────┘                     │
│         │                     │                              │
│         └─────────┬───────────┘                              │
│                   ▼                                          │
│         ┌─────────────────────┐                              │
│         │  Orchestrator       │                              │
│         │  - Task routing     │                              │
│         │  - Session mgmt     │                              │
│         │  - Budget control   │                              │
│         └─────────┬───────────┘                              │
│                   │                                          │
│         ┌─────────┴─────────────────────────┐                │
│         │                                   │                │
│         ▼                                   ▼                │
│  ┌──────────────┐                  ┌───────────────┐        │
│  │  Parliament  │                  │  Generalist   │        │
│  │  (6 Agents)  │                  │  (Architect)  │        │
│  │              │                  │               │        │
│  │ • Tech Lead  │                  │ Claude Sonnet │        │
│  │ • Architect  │◄────debate──────►│               │        │
│  │ • Coder      │                  └───────┬───────┘        │
│  │ • SRE        │                          │                │
│  │ • Security   │                          │                │
│  │ • Tester     │                          │                │
│  │              │                          │                │
│  │ Gemini 2.0   │                          │                │
│  └──────┬───────┘                          │                │
│         │                                  │                │
│         └──────────────┬───────────────────┘                │
│                        │                                    │
│                        ▼                                    │
│         ┌──────────────────────────┐                        │
│         │   Core Services Layer   │                        │
│         ├──────────────────────────┤                        │
│         │ • FileManager           │                        │
│         │ • CodebaseManager       │                        │
│         │ • MemoryManager         │                        │
│         │ • ValidationEngine      │                        │
│         │ • GitIntegration        │                        │
│         │ • ErrorCapture          │                        │
│         └──────────────────────────┘                        │
│                        │                                    │
│         ┌──────────────┴──────────────┐                     │
│         │                             │                     │
│         ▼                             ▼                     │
│  ┌─────────────┐              ┌──────────────┐             │
│  │  ChromaDB   │              │  MongoDB     │             │
│  │  - Patterns │              │  - Sessions  │             │
│  │  - Memory   │              │  - Metrics   │             │
│  │  - Code idx │              │  - State     │             │
│  └─────────────┘              └──────────────┘             │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │         Target Project                   │               │
│  │  (e.g., Maritime Broker System)          │               │
│  │  - Managed via Git                       │               │
│  │  - Incremental updates                   │               │
│  └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Principles

### 1. Error-Driven Development

**Philosophy:** Real errors are better training data than mock tests.

- **No Mocks:** Test with real services (MongoDB, Redis, Gemini API)
- **Rich Error Capture:** Every error includes full context for agent learning
- **Automatic Fixing:** Errors trigger autonomous fix-validate-deploy cycle
- **Regression Prevention:** Each fix generates a test to prevent recurrence

**Why This Works:**
```python
# Traditional approach (mocking):
@patch('redis.Redis.get')
def test_cache(mock_redis):
    mock_redis.return_value = "data"
    # Test passes but real Redis might fail

# Parliament approach (real integration):
async def test_cache():
    real_redis = Redis(host="localhost")
    result = await real_redis.get("key")
    # If fails, rich error goes to agent for fixing
```

### 2. Budget-Aware Architecture

**Target:** $10/month operational cost

**Strategy:**
- **Gemini 2.0 Flash:** 90% of operations (Parliament agents)
  - Price: $0.075/1M input tokens, $0.30/1M output tokens
  - Use case: Code implementation, testing, analysis
  
- **Claude Sonnet 4:** 10% of operations (Critical decisions)
  - Price: $3.00/1M input tokens, $15.00/1M output tokens  
  - Use case: Architecture decisions, complex refactoring

**Cost Optimization:**
```python
# Prompt caching reduces costs by 75-90%
cached_context = {
    "full_codebase": "500K tokens",  # Cached once
    "cache_reads": "50 requests/month",  # 75% discount
    "total_cost": "$0.75/month"  # vs $3.75 without cache
}
```

### 3. Multi-Agent Deliberation

**Parliament Structure:**

1. **Tech Lead Agent** (Gemini)
   - Coordinates discussion
   - Synthesizes proposals
   - Drives consensus

2. **Architect Agent** (Gemini)
   - System design
   - Scalability concerns
   - Technical debt

3. **Coder Agent** (Gemini)
   - Implementation
   - Code quality
   - Patterns

4. **SRE Agent** (Gemini)
   - Operations
   - Deployment
   - Monitoring

5. **Security Agent** (Gemini)
   - Security review
   - Vulnerability scanning
   - Best practices

6. **Tester Agent** (Gemini)
   - Test generation
   - Validation strategies
   - Quality assurance

7. **Generalist Agent** (Claude Sonnet 4)
   - High-level architecture
   - Critical decisions
   - Complex problem-solving

**Debate Process:**
```
1. Task received → All agents analyze independently
2. Each agent proposes solution from their perspective
3. Progressive persona critiques proposals
4. Critic persona challenges assumptions
5. Iterate until consensus
6. Final decision synthesis
```

### 4. Continuous Learning

**Knowledge Accumulation:**

- **Architectural Patterns:** What works in this project
- **Design Decisions:** Why we chose X over Y
- **Anti-Patterns:** What doesn't work
- **Session Learnings:** Extracted knowledge from each dev session

**Learning Loop:**
```
Session 1: Implement Redis caching (15 iterations)
  ↓
Extract pattern: "Redis HASH for entity caching"
  ↓
Store in ChromaDB with metadata
  ↓
Session 2: Similar caching task (3 iterations)
  ↓
Reuse pattern → 80% time savings
```

---

## Architectural Layers

### Layer 1: Orchestrator

**Responsibilities:**
- Session lifecycle management
- Task routing to appropriate agents
- Budget tracking and enforcement
- Consensus building from agent proposals

**Key Components:**
- `SessionManager`: Manages dev session workflow
- `TaskRouter`: Routes tasks based on complexity/type
- `BudgetController`: Enforces spending limits
- `ConsensusBuilder`: Synthesizes agent proposals

### Layer 2: Agents

**Parliament Agents (Gemini 2.0 Flash):**
Each agent has dual personas:
- **Progressive:** Proposes innovative solutions
- **Critic:** Challenges proposals, finds issues

**Generalist Agent (Claude Sonnet 4):**
- Activated for critical decisions
- Provides high-level architectural guidance
- Used sparingly due to cost

### Layer 3: Core Services

**FileManager:**
- Atomic file operations
- Backup/rollback capability
- Syntax validation before writing
- Diff generation

**CodebaseManager:**
- Maintains code context for LLMs
- Prompt caching optimization
- Dependency tracking
- Embeddings for semantic search

**MemoryManager:**
- Captures session learnings
- Stores architectural patterns
- Retrieves relevant knowledge
- Tracks pattern success rates

**ValidationEngine:**
- Syntax checking
- Type checking (mypy)
- Linting (ruff)
- Contract tests
- Smoke tests

**GitIntegration:**
- Feature branch per session
- Automatic commits
- Diff generation
- Rollback capability

**ErrorCapture:**
- Rich error context capture
- Automatic reproduction steps
- State snapshots
- Log aggregation

### Layer 4: Storage

**ChromaDB (Vector Database):**
- Architectural patterns
- Code embeddings for semantic search
- Session learnings
- Anti-patterns

**MongoDB (Document Database):**
- Dev session records
- Agent decisions
- Budget tracking
- Metrics and analytics

---

## Development Workflow

### Typical Session Flow

```
1. User: "Add Redis caching for vessel data"
   ↓
2. Orchestrator:
   - Creates session
   - Routes to relevant agents
   - Retrieves similar past implementations
   ↓
3. Parliament Debate:
   - Tech Lead: "Let's use Redis HASH structure"
   - Architect: "Consider TTL strategy"
   - Coder: "Implement with atomic operations"
   - SRE: "Add health checks"
   - Security: "Validate cache keys"
   - Tester: "Need integration tests"
   ↓
4. Consensus: Implementation plan
   ↓
5. Iteration Loop:
   - Coder implements
   - Validation engine checks
   - If fails: error capture → agent fixes
   - If passes: continue
   ↓
6. Git Integration:
   - Create feature branch
   - Commit changes
   - Generate diff
   ↓
7. Knowledge Capture:
   - Extract learnings
   - Store patterns
   - Update metrics
   ↓
8. Present to User:
   - Show diff
   - Explain decisions
   - Request approval/feedback
```

### Error-Driven Development Flow

```
Production Error:
  ↓
ErrorCapture collects:
- Stack trace
- User input
- System state
- Reproduction steps
  ↓
Send to Parliament:
  ↓
Generalist analyzes root cause
  ↓
Coder implements fix
  ↓
Tester generates regression test
  ↓
ValidationEngine verifies:
- Syntax ✓
- Types ✓
- Original error resolved ✓
- Smoke tests pass ✓
  ↓
Git commit with fix
  ↓
Deploy (auto or manual)
  ↓
Knowledge capture:
Store fix pattern for future
```

---

## Key Design Decisions

### Why Error-Driven Over TDD?

**Traditional TDD Problems:**
- Tests become legacy code (2x codebase)
- Mock maintenance burden
- Brittle tests break on refactoring
- Agents struggle with complex mocks

**Error-Driven Benefits:**
- Real errors provide perfect context
- No mock maintenance
- Tests verify actual behavior
- Agents excel at fixing concrete errors

### Why Gemini + Claude vs Single Model?

**Cost Optimization:**
```
All-Claude approach: $20+/month
  - 100 requests × $0.26/request = $26/month

Parliament approach: $6-10/month
  - 80 Gemini requests × $0.01 = $0.80
  - 20 Claude requests × $0.26 = $5.20
  - Total: $6.00/month (70% savings)
```

**Quality Trade-off:**
- Gemini 2.0 Flash: 95% as good for routine tasks
- Claude Sonnet 4: Superior for architecture
- Hybrid: Best cost/quality ratio

### Why ChromaDB + MongoDB vs Single DB?

**ChromaDB (Vector):**
- Optimized for semantic search
- Fast pattern retrieval
- Embeddings for code

**MongoDB (Document):**
- Structured session data
- Time-series metrics
- Complex queries

**Separation Benefits:**
- Each DB used for its strengths
- Better performance
- Simpler data models

### Why Real Services Over Mocks in Tests?

**Testing Philosophy:**
```
Mock approach:
- Fast (milliseconds)
- Isolated
- Brittle
- Misleading confidence

Real integration approach:
- Slower (seconds)
- Catches real issues
- Robust
- True confidence
```

**Cost of Real Services:**
- MongoDB: Free tier sufficient
- Redis: Docker container (free)
- ChromaDB: Docker container (free)
- Gemini API: ~$0.05 per test run

**Verdict:** Real integration worth the extra seconds

---

## Success Metrics

### Learning Progress

```python
# Month 1 (Cold Start):
{
    "avg_iterations_per_task": 12.5,
    "patterns_learned": 5,
    "time_to_solution": "2.5 hours"
}

# Month 3 (Learning):
{
    "avg_iterations_per_task": 6.2,
    "patterns_learned": 25,
    "time_to_solution": "45 minutes",
    "pattern_reuse_rate": 0.65
}

# Month 6 (Experienced):
{
    "avg_iterations_per_task": 3.1,
    "patterns_learned": 60,
    "time_to_solution": "20 minutes",
    "pattern_reuse_rate": 0.85
}
```

### Cost Efficiency

```python
TARGET_MONTHLY_COST = {
    "gemini_api": "$4-6",
    "claude_api": "$2-4",
    "infrastructure": "$0 (free tiers)",
    "total": "$6-10"
}

COMPARISON = {
    "cursor_pro": "$20/month",
    "copilot": "$10/month + IDE required",
    "parliament": "$10/month + autonomous"
}
```

### Quality Metrics

```python
QUALITY_GOALS = {
    "error_fix_success_rate": "> 90%",
    "regression_prevention": "> 95%",
    "code_quality_score": "> 85",
    "test_coverage": "Critical paths only (20-30 tests)"
}
```

---

## Technology Agnosticism

While initially built for Python projects, Parliament is designed to be language-agnostic:

**Supported (Phase 1):**
- Python (primary)
- Docker
- Shell scripts

**Planned (Phase 2):**
- JavaScript/TypeScript
- Go
- Rust

**How It Works:**
```python
# Language detection
file_extension = get_file_extension(filepath)

# Route to appropriate validation
if file_extension == '.py':
    validator = PythonValidator()
elif file_extension == '.js':
    validator = JavaScriptValidator()
elif file_extension == '.go':
    validator = GoValidator()

# Validation interface is consistent
result = await validator.validate(code)
```

---

## Future Enhancements

### Phase 1 (MVP) - Current Focus
- ✅ Architecture design
- 🚧 Core services implementation
- 🚧 Parliament agents
- 🚧 Error capture system
- 🚧 CLI interface

### Phase 2 (Enhancement)
- [ ] Web UI for monitoring
- [ ] Prometheus metrics
- [ ] Multi-language support
- [ ] Cloud deployment automation
- [ ] Team collaboration features

### Phase 3 (Advanced)
- [ ] Self-improving agents
- [ ] Meta-learning across projects
- [ ] Predictive issue detection
- [ ] Automated performance optimization
- [ ] Cross-project knowledge sharing

---

## Comparison with Existing Tools

### vs Cursor

| Feature | Cursor | Parliament |
|---------|--------|------------|
| **Cost** | $20/month | $10/month |
| **Model** | Claude only | Gemini + Claude hybrid |
| **Testing** | Manual | Automated error-driven |
| **Learning** | Per-session | Continuous across sessions |
| **Multi-agent** | No | Yes (Parliament) |
| **Autonomy** | Human-in-loop | Autonomous with oversight |

### vs GitHub Copilot

| Feature | Copilot | Parliament |
|---------|---------|------------|
| **Cost** | $10/month | $10/month |
| **Scope** | Code completion | Full development cycle |
| **Testing** | None | Integrated |
| **Architecture** | No | Yes (multi-agent) |
| **Learning** | Global model | Project-specific |
| **Debugging** | Limited | Autonomous error fixing |

### vs Cursor + Copilot

Parliament provides comparable functionality to using both tools while:
- Costing less ($10 vs $30/month)
- Providing autonomous operation
- Learning from your specific project
- Handling full development lifecycle

---

## Security & Privacy

### Code Privacy
- All code stays local or in your cloud
- LLM APIs see only what you send
- No code retention by default (check LLM provider policies)

### API Key Management
- Store in environment variables
- Never commit to git
- Rotate regularly
- Use separate keys for dev/prod

### Error Reporting
- Configurable sensitivity levels
- PII redaction before sending to LLMs
- Option to disable automatic error reporting

---

## Getting Started

### Quick Start

```bash
# 1. Install Parliament
pip install parliament-dev

# 2. Initialize project
parliament init /path/to/your/project

# 3. Configure
export GEMINI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

# 4. Start development
parliament dev "Add Redis caching for user sessions"

# 5. Monitor for errors (optional)
parliament monitor --auto-fix
```

### Configuration

```yaml
# .parliament/config.yaml
project_name: "Maritime Broker System"
budget:
  monthly_limit_usd: 10.0
  alert_threshold: 0.8
models:
  parliament: "gemini-2.0-flash-exp"
  generalist: "claude-sonnet-4-20250514"
behavior:
  auto_fix_errors: true
  require_approval: true
  max_iterations: 20
storage:
  vector_db: "chromadb"
  document_db: "mongodb"
```

---

## Support & Resources

### Documentation
- Full API reference: `/docs/api.md`
- Development guide: `/docs/development.md`
- Architecture deep-dive: `/docs/architecture-deep-dive.md`

### Community
- GitHub: `github.com/your-org/parliament-dev`
- Discord: `discord.gg/parliament`
- Issues: `github.com/your-org/parliament-dev/issues`

### Contributing
- Contribution guide: `/CONTRIBUTING.md`
- Code of conduct: `/CODE_OF_CONDUCT.md`
- Development setup: `/docs/development-setup.md`

---

## Conclusion

Parliament represents a new paradigm in autonomous development:

1. **Error-Driven:** Learn from real failures, not mock scenarios
2. **Budget-Conscious:** $10/month for professional development tools
3. **Continuously Learning:** Gets better with every session
4. **Multi-Agent:** Diverse perspectives lead to better solutions
5. **Autonomous:** Handles routine tasks while keeping human in control

**Current Status:** Architecture complete, implementation in progress  
**Timeline:** MVP targeted for Q1 2026  
**Test Case:** Maritime broker system (production-ready)

---

*Last Updated: 2026-01-25*  
*Version: 1.0*  
*Status: Active Development*

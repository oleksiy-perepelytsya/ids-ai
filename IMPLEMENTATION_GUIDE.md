# Phase 1 - Remaining Implementation Guide

This document outlines the remaining files needed to complete Phase 1.

## Status: ~70% Complete

### ✅ Completed
- Project setup (Docker, Poetry, config)
- Data models (CROSS, Agent, Session, Project, Consensus)
- Configuration system (settings, thresholds)
- Storage layer (MongoDB, ChromaDB interfaces)
- LLM client (Gemini + Claude)
- Agent personas (YAML configs for all 7 agents)
- Documentation (README)

### 🔄 Remaining to Implement

## 1. Agent System (`ids/agents/`)

### `base_agent.py`
```python
"""
Base agent class that all agents inherit from.
Responsibilities:
- Load persona from YAML
- Parse CROSS scores from LLM response
- Format prompts with task context
- Handle LLM API calls via LLMClient
"""

Key methods:
- __init__(role: AgentRole, llm_client: LLMClient)
- load_persona() -> Dict
- analyze(task: str, context: str, previous_rounds: List) -> AgentResponse
- _parse_cross_scores(response_text: str) -> CrossScore
- _extract_concerns(response_text: str) -> List[str]
```

### `generalist.py`
```python
"""
Generalist agent (Claude-based orchestrator).
Responsibilities:
- Provide initial high-level analysis
- Synthesize agent responses
- Make consensus decisions
"""

Inherits from BaseAgent with role=GENERALIST
Uses Claude via llm_client.call_claude()
```

### `developer.py`, `architect.py`, `sre.py`
```python
"""
Specialized agents (Gemini-based).
Each has progressive and critic personas.
Responsibilities:
- Analyze from their role perspective
- Provide CROSS scores
- Propose approaches
- Identify concerns
"""

Each inherits from BaseAgent
Progressive uses persona: developer_progressive.yaml
Critic uses persona: developer_critic.yaml
Uses Gemini via llm_client.call_gemini()
```

### `__init__.py`
Export all agent classes.

## 2. Orchestrator (`ids/orchestrator/`)

### `consensus_builder.py`
```python
"""
Evaluates CROSS scores and determines consensus/continue/dead-end.
Responsibilities:
- Merge agent CROSS scores
- Compare against thresholds (from thresholds.yaml)
- Detect consensus patterns
- Detect dead-end patterns
"""

Key methods:
- evaluate_round(round_result: RoundResult, round_num: int) -> DecisionResult
- _merge_scores(responses: List[AgentResponse]) -> MergedCross
- _check_consensus(merged: MergedCross, round_num: int) -> bool
- _detect_dead_end(session: DevSession) -> bool
```

### `round_executor.py`
```python
"""
Executes a single deliberation round.
Responsibilities:
- Get Generalist initial analysis
- Call all 6 specialized agents in parallel
- Collect responses
- Return RoundResult
"""

Key methods:
- execute_round(session: DevSession, round_num: int) -> RoundResult
- _get_generalist_analysis(task, context) -> CrossScore
- _get_agent_responses(task, context, generalist_cross) -> List[AgentResponse]
```

### `session_manager.py`
```python
"""
Manages complete deliberation sessions.
Responsibilities:
- Create new sessions
- Run multi-round deliberation
- Handle user feedback on dead-ends
- Update session status
- Persist to storage
"""

Key methods:
- create_session(user_id, chat_id, task, project) -> DevSession
- run_deliberation(session: DevSession) -> DeliberationResult
- handle_dead_end_feedback(session: DevSession, feedback: str)
- continue_session(session_id: str)
```

### `__init__.py`
Export ConsensusBuilder, RoundExecutor, SessionManager

## 3. Telegram Interface (`ids/interfaces/telegram/`)

### `bot.py`
```python
"""
Telegram bot initialization and setup.
Responsibilities:
- Create Telegram Application
- Register all handlers
- Start polling
"""

Key methods:
- create_bot() -> Application
- setup_handlers(app: Application)
- start()
```

### `handlers.py`
```python
"""
All Telegram command and message handlers.
Responsibilities:
- Handle /start, /help, /register_project, etc.
- Handle text messages (task submission)
- Handle callback buttons
"""

Key functions:
- cmd_start(update, context)
- cmd_register_project(update, context)
- cmd_project(update, context)
- cmd_list_projects(update, context)
- handle_message(update, context)  # Task submission
- handle_dead_end_feedback(update, context)
```

### `formatters.py`
```python
"""
Format data for Telegram display.
Responsibilities:
- Format CROSS scores nicely
- Format round results
- Format consensus decisions
- Format errors
"""

Key functions:
- format_cross_scores(scores: List[CrossScore]) -> str
- format_round_result(round: RoundResult) -> str
- format_consensus(decision: str, explanation: str) -> str
- format_agent_response(response: AgentResponse) -> str
```

### `keyboards.py`
```python
"""
Telegram inline keyboards for interactions.
Responsibilities:
- Create button layouts
- Handle callback data
"""

Key functions:
- get_dead_end_keyboard() -> InlineKeyboardMarkup
- get_project_list_keyboard(projects: List) -> InlineKeyboardMarkup
- get_settings_keyboard() -> InlineKeyboardMarkup
```

### `__init__.py`
Export bot creation and handler functions.

## 4. Main Entry Point

### `ids/__init__.py`
```python
"""Package initialization"""
__version__ = "0.1.0"
```

### `ids/__main__.py`
```python
"""
Main entry point for IDS application.
Responsibilities:
- Setup logging
- Initialize storage
- Initialize LLM client
- Initialize agents
- Initialize orchestrator
- Start Telegram bot
"""

if __name__ == "__main__":
    # Setup
    setup_logging()
    
    # Initialize components
    llm_client = LLMClient()
    session_store = MongoSessionStore()
    project_store = MongoProjectStore()
    chroma_store = ChromaStore()
    
    # Initialize orchestrator
    session_manager = SessionManager(
        llm_client=llm_client,
        session_store=session_store,
        ...
    )
    
    # Start bot
    bot = create_bot(session_manager)
    bot.run_polling()
```

## 5. Testing (`tests/`)

### `conftest.py`
Pytest fixtures for testing:
- Mock LLM responses
- Test database connections
- Sample sessions/projects

### `test_models.py`
Unit tests for data models:
- CROSS score validation
- MergedCross calculation
- Session model operations

### `test_consensus.py`
Test consensus builder:
- Threshold evaluation
- Dead-end detection
- Score merging

### `test_agents.py`
Test agent system:
- Persona loading
- CROSS score parsing
- Agent response formatting

### `test_telegram.py`
Integration tests for Telegram:
- Command handling
- Message processing
- Session creation

### `test_integration.py`
Full end-to-end tests:
- Complete deliberation flow
- Multi-round consensus
- Dead-end handling

## Implementation Order Recommendation

1. **Base Agent + Agent Implementations** (2-3 days)
   - Start here as it's core to system
   - Test with real LLM APIs
   - Validate CROSS parsing

2. **Consensus Builder** (1 day)
   - Relatively straightforward
   - Load thresholds from YAML
   - Implement evaluation logic

3. **Round Executor** (1 day)
   - Orchestrate agent calls
   - Handle parallel execution
   - Collect results

4. **Session Manager** (1-2 days)
   - Tie everything together
   - Handle multi-round flow
   - Integrate with storage

5. **Telegram Interface** (2-3 days)
   - Bot setup
   - All command handlers
   - Formatters for display
   - Interactive keyboards

6. **Main Entry Point** (0.5 day)
   - Wire everything together
   - Startup sequence
   - Error handling

7. **Testing** (1-2 days)
   - Integration tests
   - End-to-end validation
   - Fix bugs

## Total Estimated Time: 8-12 days

## Key Implementation Notes

### CROSS Parsing
Agent responses must follow strict format:
```
CROSS SCORES:
Confidence: 85
Risk: 25
Outcome: 80

ANALYSIS:
...

PROPOSED APPROACH:
...

CONCERNS:
- Concern 1
- Concern 2
```

Use regex or structured parsing to extract scores.

### Parallel Agent Calls
Use asyncio.gather() to call all 6 agents simultaneously:
```python
agent_tasks = [
    agent.analyze(task, context) 
    for agent in specialized_agents
]
responses = await asyncio.gather(*agent_tasks)
```

### Error Handling
Wrap all LLM calls in try/except:
- Log errors
- Retry on transient failures
- Notify user on persistent failures

### Telegram Rate Limits
Be mindful of:
- Message rate limits (30 msg/sec per chat)
- Callback query rate limits
- Use `send_chat_action(TYPING)` for long operations

### Storage Patterns
Always use async/await:
```python
session = await session_store.create_session(new_session)
await session_store.update_session(session)
```

## Next Steps After Phase 1

Once Phase 1 is complete and tested:

1. Deploy to production
2. Collect real usage data
3. Tune thresholds based on results
4. Gather user feedback
5. Plan Phase 2 (code manipulation features)

## Questions/Decisions Needed

Before implementing remaining files:

1. Should agents be called in parallel or sequentially?
   - **Recommend:** Parallel for speed

2. How to handle LLM API failures?
   - **Recommend:** Retry 3x, then notify user

3. Should round updates be real-time or batched?
   - **Recommend:** Real-time with send_chat_action(TYPING)

4. Maximum session duration?
   - **Recommend:** 30 minutes timeout

5. Store LLM responses for debugging?
   - **Recommend:** Yes, in MongoDB with session

## Files Checklist

- [ ] ids/agents/base_agent.py
- [ ] ids/agents/generalist.py
- [ ] ids/agents/developer.py
- [ ] ids/agents/architect.py
- [ ] ids/agents/sre.py
- [ ] ids/agents/__init__.py
- [ ] ids/orchestrator/consensus_builder.py
- [ ] ids/orchestrator/round_executor.py
- [ ] ids/orchestrator/session_manager.py
- [ ] ids/orchestrator/__init__.py
- [ ] ids/interfaces/telegram/bot.py
- [ ] ids/interfaces/telegram/handlers.py
- [ ] ids/interfaces/telegram/formatters.py
- [ ] ids/interfaces/telegram/keyboards.py
- [ ] ids/interfaces/telegram/__init__.py
- [ ] ids/__init__.py
- [ ] ids/__main__.py
- [ ] tests/conftest.py
- [ ] tests/test_models.py
- [ ] tests/test_consensus.py
- [ ] tests/test_agents.py
- [ ] tests/test_telegram.py
- [ ] tests/test_integration.py

Once all files are implemented, Phase 1 will be complete!

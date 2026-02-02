# IDS (Intelligent Development System) - Phase 1

Multi-agent AI deliberation system via Telegram. Uses Parliament architecture with CROSS scoring for consensus building.

## Features (Phase 1)

✅ **Telegram Interface** - Remote control via Telegram bot
✅ **Multi-Agent System** - 1 Generalist (Claude) + 6 Specialized agents (Gemini)
✅ **CROSS Scoring** - Confidence, Risk, Outcome scoring (0-100)
✅ **Consensus Building** - Multi-round deliberation with tunable thresholds
✅ **Multi-Project Support** - Switch between different decision contexts
✅ **Session Management** - Track deliberation history
✅ **Dead-End Detection** - Request user feedback when stuck

## Architecture

```
User (Telegram) → Bot → Session Manager → Deliberation Rounds
                                              ↓
                                    [Generalist (Claude)]
                                              ↓
                    ┌─────────────────────────┴─────────────────────────┐
                    ↓                         ↓                         ↓
          [Developer P/C (Gemini)]  [Architect P/C (Gemini)]  [SRE P/C (Gemini)]
                    ↓                         ↓                         ↓
                                    [Consensus Builder]
                                              ↓
                            [Decision: Consensus/Continue/Dead-End]
```

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Telegram Bot Token (get from @BotFather)
- Gemini API Key (get from Google AI Studio)
- Claude API Key (get from Anthropic Console)

### 2. Setup

```bash
# Clone/create project
mkdir ids && cd ids

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

### 3. Configure .env

```bash
# Required: Your API keys and bot token
TELEGRAM_BOT_TOKEN=123456789:ABC...
GEMINI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Required: Whitelist your Telegram user ID
# To get your ID, message @userinfobot on Telegram
ALLOWED_TELEGRAM_USERS=12345,67890

# Optional: Adjust behavior
ROUND_LOGGING=true  # Show detailed round updates
MAX_ROUNDS=3        # Maximum deliberation rounds
```

### 4. Start Services

```bash
# Start all containers
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f ids
```

### 5. Use via Telegram

```
Start conversation with your bot:

You: /start
Bot: 👋 Welcome to IDS! Register a project or ask a question.

You: /register_project maritime Maritime business decisions
Bot: ✅ Project 'maritime' registered

You: /project maritime
Bot: 📂 Switched to project: maritime

You: Should we accept this charter offer at $45k/day for 6 months?
Bot: 🏛️ Starting Parliament deliberation...
     [Round 1 in progress...]
```

## Commands

### Project Management
- `/start` - Initialize bot
- `/help` - Show available commands
- `/register_project <name> <description>` - Register new project
- `/project <name>` - Switch to project
- `/list_projects` - Show your projects

### Session Management
- `/status` - Show current session status
- `/continue` - Continue previous session
- `/cancel` - Cancel current session
- `/history` - View past deliberations

### Settings
- `/settings` - View/change settings
- Toggle round logging ON/OFF

## How It Works

### 1. Submit Question/Task
Send any question or decision you need help with:
- Business decisions
- Technical architecture
- Problem solving
- Strategy planning

### 2. Parliament Deliberates
The system runs multi-round deliberation:

**Round 1:**
- Generalist (Claude) analyzes and provides initial CROSS score
- 6 specialized agents (Gemini) each analyze with their perspective:
  - Developer Progressive: Pragmatic implementation view
  - Developer Critic: Identifies risks and edge cases
  - Architect Progressive: System design and scalability
  - Architect Critic: Questions complexity and coupling
  - SRE Progressive: Operational reliability
  - SRE Critic: Failure modes and resource concerns

**Each agent provides:**
- Confidence: 0-100 (how confident in solution)
- Risk: 0-100 (0=safe, 100=critical risk)
- Outcome: 0-100 (0=poor, 100=excellent expected result)
- Explanation: Detailed reasoning
- Proposed approach: Specific solution
- Concerns: Issues identified

### 3. Consensus Check
Generalist merges all CROSS scores and checks:
- Is average confidence high enough?
- Are risks manageable?
- Are expected outcomes good enough?
- Do agents agree (low standard deviation)?

**If YES** → Consensus reached, final decision provided
**If PROGRESS** → Continue to Round 2 with updated context
**If STUCK** → Dead-end, request user guidance

### 4. User Feedback (if dead-end)
If agents can't reach consensus, you'll be asked:
- Provide additional guidance
- Choose between conflicting approaches
- Restart with new direction

## Example Session

```
User: Should we use microservices or monolith for maritime broker?

Bot: 🏛️ Round 1 starting...

[After deliberation]

Bot: 📊 Round 1 Results:
     Avg Confidence: 68%
     Max Risk: 45%
     Avg Outcome: 65%
     
     Main debate: Developer wants monolith for simplicity,
     Architect suggests modular approach for future scaling.
     
     Continuing to Round 2...

[Round 2]

Bot: 📊 Round 2 Results:
     Avg Confidence: 82%
     Max Risk: 25%
     Avg Outcome: 80%
     
     ✅ Consensus reached!

Bot: 📋 DECISION: Start with Modular Monolith
     
     RATIONALE:
     - Begin with single deployment for simplicity
     - Structure code as modules with clear boundaries
     - Easy to extract microservices later if needed
     - Balances current simplicity with future flexibility
     
     KEY CONSIDERATIONS:
     - Use dependency injection for loose coupling
     - Keep module interfaces well-defined
     - Avoid shared state between modules
     - Plan migration strategy upfront
     
     RISKS MITIGATED:
     - Avoid premature microservices complexity
     - Maintain ability to scale later
     - Keep initial development velocity high
```

## Configuration

### Tunable Thresholds
Edit `ids/config/thresholds.yaml` to adjust consensus thresholds:

```yaml
consensus:
  confidence_threshold:
    round_1: 85.0  # Strict initially
    round_2: 75.0  # Moderate
    round_3: 70.0  # Lenient
    
  max_acceptable_risk:
    round_1: 20.0  # Risk-averse
    round_2: 30.0
    round_3: 40.0
```

These can be tuned based on your experience with the system.

## Development

### Project Structure
```
ids/
├── ids/
│   ├── models/          # Data models (CROSS, Agent, Session)
│   ├── agents/          # Agent implementations + personas
│   ├── orchestrator/    # Session management, consensus
│   ├── services/        # LLM client
│   ├── storage/         # MongoDB, ChromaDB
│   ├── interfaces/      # Telegram bot
│   ├── config/          # Settings, thresholds
│   └── utils/           # Logging
├── tests/               # Integration tests
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

### Running Tests
```bash
docker-compose exec ids pytest
```

### Viewing Logs
```bash
# All logs
docker-compose logs -f ids

# Just errors
docker-compose logs ids | grep ERROR

# MongoDB logs
docker-compose logs -f mongodb
```

## Troubleshooting

### Bot not responding
1. Check bot token is correct in `.env`
2. Verify your user ID is in `ALLOWED_TELEGRAM_USERS`
3. Check logs: `docker-compose logs ids`

### API errors
1. Verify API keys are valid
2. Check API quotas/limits
3. See logs for specific error messages

### Container issues
```bash
# Restart services
docker-compose restart

# Rebuild if code changed
docker-compose up -d --build

# Reset everything
docker-compose down -v
docker-compose up -d
```

## Roadmap

### Phase 1 (Current)
- ✅ Telegram interface
- ✅ Multi-agent deliberation
- ✅ CROSS scoring
- ✅ Consensus building
- ✅ Session management

### Phase 2 (Next)
- 🔄 Code writing/modification
- 🔄 Git integration
- 🔄 Validation engine
- 🔄 File operations
- 🔄 Codebase caching

### Phase 3 (Future)
- 📅 Auto-fixing
- 📅 Pattern learning
- 📅 Cross-project knowledge
- 📅 CLI interface

## Support

For issues or questions:
1. Check logs: `docker-compose logs ids`
2. Verify configuration in `.env`
3. Review this README

## License

[Your License Here]

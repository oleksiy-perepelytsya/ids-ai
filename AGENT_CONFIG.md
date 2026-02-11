# Agent Enable/Disable Configuration

You can now selectively enable or disable specialist agents in the Parliament to customize the deliberation process.

## Configuration

Add these settings to your `.env` file:

```bash
# Agent Enable/Disable (set to false to disable specific agents)
DEVELOPER_PROGRESSIVE_ENABLED=true
DEVELOPER_CRITIC_ENABLED=true
ARCHITECT_PROGRESSIVE_ENABLED=true
ARCHITECT_CRITIC_ENABLED=true
SRE_PROGRESSIVE_ENABLED=true
SRE_CRITIC_ENABLED=true
```

## Use Cases

### 1. Reduce API Costs
Disable some agents to reduce the number of LLM API calls per deliberation:

```bash
# Only use Developer agents (2 agents instead of 6)
DEVELOPER_PROGRESSIVE_ENABLED=true
DEVELOPER_CRITIC_ENABLED=true
ARCHITECT_PROGRESSIVE_ENABLED=false
ARCHITECT_CRITIC_ENABLED=false
SRE_PROGRESSIVE_ENABLED=false
SRE_CRITIC_ENABLED=false
```

### 2. Faster Responses
Fewer agents mean faster deliberation rounds:

```bash
# Use only Progressive agents (3 agents instead of 6)
DEVELOPER_PROGRESSIVE_ENABLED=true
DEVELOPER_CRITIC_ENABLED=false
ARCHITECT_PROGRESSIVE_ENABLED=true
ARCHITECT_CRITIC_ENABLED=false
SRE_PROGRESSIVE_ENABLED=true
SRE_CRITIC_ENABLED=false
```

### 3. Focused Expertise
Enable only agents relevant to your use case:

```bash
# Architecture-focused (only Architect agents)
DEVELOPER_PROGRESSIVE_ENABLED=false
DEVELOPER_CRITIC_ENABLED=false
ARCHITECT_PROGRESSIVE_ENABLED=true
ARCHITECT_CRITIC_ENABLED=true
SRE_PROGRESSIVE_ENABLED=false
SRE_CRITIC_ENABLED=false
```

### 4. Development vs Production
Use different configurations for different environments:

**Development (.env.dev):**
```bash
# Faster, cheaper - only 2 agents
DEVELOPER_PROGRESSIVE_ENABLED=true
DEVELOPER_CRITIC_ENABLED=true
ARCHITECT_PROGRESSIVE_ENABLED=false
ARCHITECT_CRITIC_ENABLED=false
SRE_PROGRESSIVE_ENABLED=false
SRE_CRITIC_ENABLED=false
```

**Production (.env.prod):**
```bash
# Full deliberation - all 6 agents
DEVELOPER_PROGRESSIVE_ENABLED=true
DEVELOPER_CRITIC_ENABLED=true
ARCHITECT_PROGRESSIVE_ENABLED=true
ARCHITECT_CRITIC_ENABLED=true
SRE_PROGRESSIVE_ENABLED=true
SRE_CRITIC_ENABLED=true
```

## Agent Roles

- **Developer Progressive**: Proposes practical implementation approaches
- **Developer Critic**: Identifies code quality and maintainability issues
- **Architect Progressive**: Suggests architectural patterns and system design
- **Architect Critic**: Evaluates scalability and design trade-offs
- **SRE Progressive**: Recommends operational and reliability improvements
- **SRE Critic**: Highlights deployment and monitoring concerns

## Important Notes

1. **Generalist is always enabled** - It's required for the deliberation process
2. **At least one specialist should be enabled** - Otherwise deliberation won't be meaningful
3. **Changes require restart** - After modifying `.env`, restart the bot:
   ```bash
   docker compose restart ids
   ```

## Verification

Check the startup logs to see which agents are enabled:

```bash
docker compose logs ids | grep ids_ready
```

You should see output like:
```json
{
  "event": "ids_ready",
  "total_agents": 3,
  "enabled_specialists": ["developer_progressive", "developer_critic"]
}
```

## Performance Impact

| Agents Enabled | API Calls per Round | Approximate Time (Sequential) |
|----------------|---------------------|-------------------------------|
| 6 (all)        | 7                   | ~14 seconds                   |
| 4              | 5                   | ~10 seconds                   |
| 2              | 3                   | ~6 seconds                    |
| 1              | 2                   | ~4 seconds                    |

*Times assume 2-second delay between calls (AGENT_DELAY_SECONDS=2.0)*

---

## Customizing Agent Personas

Agent behaviors are defined in Markdown files located in `ids/agents/personas/`. You can edit these files to change how agents think and respond.

### New Markdown Format

To avoid YAML parsing issues, we now use a simple Markdown format:

```md
# Role: [Agent Name]

# System Prompt
[The instructions for the agent]
```

### Files
- `generalist.md`
- `developer_progressive.md`
- `developer_critic.md`
- `architect_progressive.md`
- `architect_critic.md`
- `sre_progressive.md`
- `sre_critic.md`

### How to Edit
1. Open the `.md` file for the agent you want to customize.
2. Update the `# System Prompt` section with new instructions.
3. Save the file.
4. Restart the bot for changes to take effect:
   ```bash
   docker compose restart ids
   ```


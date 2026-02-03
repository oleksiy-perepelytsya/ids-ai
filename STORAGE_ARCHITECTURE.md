# IDS Storage Architecture

## Overview

IDS uses two complementary storage systems:
1. **MongoDB** - Primary storage for all session data
2. **ChromaDB** - Semantic search for codebase caching (Phase 2/3)

---

## MongoDB: Session & Conversation Storage

### What's Stored

**Complete deliberation history** including:
- User's task and context
- Every round of deliberation
- Generalist's prompt to parliament each round
- All 6 parliament member responses (full text + CROSS scores)
- Merged CROSS scores
- Decision outcome and reasoning

### Data Structure

```python
DevSession {
    session_id: str
    telegram_user_id: int
    task: str
    context: str  # User guidance accumulated
    
    rounds: [
        RoundResult {
            round_number: int
            
            # What generalist sent to parliament
            generalist_prompt: str  # NEW in this update
            generalist_cross: CrossScore
            
            # All agent responses
            agent_responses: [
                AgentResponse {
                    agent_id: AgentRole
                    raw_response: str  # NEW: Full LLM response
                    cross_score: CrossScore
                    proposed_approach: str
                    concerns: [str]
                }
            ]
            
            # Aggregated results
            merged_cross: MergedCross
            decision: DecisionResult
            decision_reasoning: str  # NEW in this update
        }
    ]
    
    status: SessionStatus
    created_at: datetime
}
```

### New Fields Added

**RoundResult:**
- ✨ `generalist_prompt` - Prompt sent by generalist to parliament members
- ✨ `decision_reasoning` - Why the decision (CONSENSUS/CONTINUE/DEAD_END) was made

**AgentResponse:**
- ✨ `raw_response` - Complete LLM response before parsing

### How to Access Full Conversations

#### Method 1: Via Telegram Bot

```
/export 1     # Export most recent session
/export 3     # Export 3rd most recent
```

This exports the complete conversation in Markdown format showing:
- Task and context
- Each round's generalist prompt
- All agent responses (full text)
- CROSS scores from all agents
- Merged scores and decisions
- Final outcome

#### Method 2: Via API (Python)

```python
from ids.storage import MongoSessionStore
from ids.utils.conversation_export import ConversationExporter

# Get session
store = MongoSessionStore()
session = await store.get_session("sess_abc123")

# Export to Markdown
markdown = ConversationExporter.export_to_markdown(session)
print(markdown)

# Or get JSON
json_data = ConversationExporter.export_to_json(session)

# Or brief summary
summary = ConversationExporter.get_conversation_summary(session)
```

#### Method 3: Direct MongoDB Query

```javascript
// Connect to MongoDB
use ids;

// Get session with all rounds
db.sessions.findOne({session_id: "sess_abc123"});

// Find all sessions for a user
db.sessions.find({telegram_user_id: 12345})
  .sort({created_at: -1})
  .limit(10);

// Count rounds per session
db.sessions.aggregate([
  {$project: {
    session_id: 1,
    round_count: {$size: "$rounds"}
  }}
]);
```

---

## ChromaDB: Codebase Semantic Search

### What's Stored

**Project codebases** for semantic search (Phase 2/3):
- Python source files
- File paths and metadata
- Embeddings for similarity search

### Purpose

NOT for conversation storage. Used for:
1. Finding relevant files when generating code
2. Caching entire codebase for LLM context
3. Semantic search: "Find files related to authentication"

### Collections

```
codebase_<project_id>
- documents: File contents
- metadata: {filepath, project_id}
- ids: "<project_id>:<filepath>"
```

### Example Usage

```python
from ids.storage import ChromaStore

chroma = ChromaStore()
await chroma.initialize()

# Cache project
await chroma.cache_codebase(
    project_id="maritime",
    files={
        "app/main.py": "...",
        "app/models.py": "..."
    }
)

# Search for relevant files
results = await chroma.search_codebase(
    project_id="maritime",
    query="authentication and JWT tokens",
    n_results=5
)

# Get complete codebase
full_code = await chroma.get_full_codebase("maritime")
```

---

## Data Flow

### Deliberation Session Flow

```
User sends question
    ↓
SessionManager creates DevSession in MongoDB
    ↓
Round 1:
    ↓
  Generalist creates prompt → stored in RoundResult.generalist_prompt
    ↓
  Generalist produces CROSS → stored in RoundResult.generalist_cross
    ↓
  Parliament members respond → each response stored in agent_responses
    (includes raw_response, cross_score, proposed_approach)
    ↓
  CROSS scores merged → stored in RoundResult.merged_cross
    ↓
  Decision made → stored in RoundResult.decision + decision_reasoning
    ↓
Round added to session.rounds[]
    ↓
Session updated in MongoDB
    ↓
If CONSENSUS or DEAD_END → session complete
If CONTINUE → next round
```

### Code Generation Flow (Phase 2)

```
User: /code Add caching
    ↓
Deliberation (as above, stored in MongoDB)
    ↓
Consensus reached on approach
    ↓
ChromaDB: Search relevant files in project
    ↓
Generate Python code with context
    ↓
Validate and write
    ↓
(Future: Store pattern in ChromaDB)
```

---

## Storage Queries

### Common MongoDB Queries

```python
# Get active sessions
sessions = await store.get_user_sessions(user_id, limit=10)

# Get specific session
session = await store.get_session("sess_abc123")

# Get currently active (in-progress)
active = await store.get_active_session(user_id)

# Find sessions by project
# (Not implemented yet - add if needed)

# Find consensus sessions
# (Not implemented yet - add if needed)
```

### Common ChromaDB Queries

```python
# Search codebase
results = await chroma.search_codebase(
    project_id="maritime",
    query="database connection",
    n_results=5
)

# Get full codebase
code = await chroma.get_full_codebase("maritime")
```

---

## Viewing Conversations

### Via Telegram

1. Get session list:
```
/history
```

2. Export full conversation:
```
/export 1
```

Output includes:
- Task description
- Every round's prompts and responses
- All CROSS scores
- Decision reasoning
- Timeline

### Via MongoDB Compass (GUI)

1. Connect to MongoDB
2. Navigate to `ids` database → `sessions` collection
3. View session documents with full round details

### Via Export Utility

```python
from ids.utils.conversation_export import ConversationExporter

# Markdown format (readable)
markdown = ConversationExporter.export_to_markdown(session)
with open("conversation.md", "w") as f:
    f.write(markdown)

# JSON format (structured)
json_data = ConversationExporter.export_to_json(session)
import json
with open("conversation.json", "w") as f:
    json.dump(json_data, f, indent=2)
```

---

## Performance Considerations

### MongoDB

**Indexes recommended:**
```javascript
db.sessions.createIndex({telegram_user_id: 1, created_at: -1});
db.sessions.createIndex({session_id: 1});
db.sessions.createIndex({status: 1});
```

**Document size:**
- Average session: 50-200 KB
- Large session (10 rounds): ~500 KB
- No size issues expected for normal usage

### ChromaDB

**Collection size:**
- Per project: 1-10 MB (typical)
- Large project (1000+ files): 50-100 MB
- Embeddings cached for fast search

---

## Backup Strategy

### MongoDB Backup

```bash
# Dump all sessions
mongodump --uri="mongodb://localhost:27017" --db=ids --out=/backup

# Restore
mongorestore --uri="mongodb://localhost:27017" --dir=/backup
```

### ChromaDB Backup

```bash
# Backup ChromaDB data directory
tar -czf chroma-backup.tar.gz /path/to/chroma_data/
```

---

## Summary

✅ **MongoDB stores EVERYTHING:**
- Complete deliberation history
- All prompts and responses
- All CROSS scores
- Decision reasoning
- Full conversation flow

✅ **ChromaDB stores:**
- Project codebases (Phase 2/3)
- For semantic search and context
- NOT for conversations

✅ **New /export command:**
- Export any past session
- Complete conversation in Markdown
- All agent responses included
- Easy to follow the deliberation flow

---

**Updated:** 2026-02-02  
**Version:** Phase 2 with Enhanced Storage

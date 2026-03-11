# Memory System

## Overview

The memory layer is now split into four coordinated memory types:

1. ShortTermMemory
- In-process rolling buffer per user.
- Used for immediate conversational continuity during runtime.

2. ConversationMemory
- SQLite-backed interaction storage.
- Stores each completed turn with:
  - user_message
  - assistant_response
  - timestamp
  - session_id
- Also keeps role-based messages for prompt assembly.

3. LongTermMemory
- SQLite-backed durable fact store for personal knowledge.
- Entry fields:
  - id
  - content
  - tags
  - importance_score (1-10)
  - created_at
  - expires_at (optional)
  - is_sensitive
- Sensitive facts are encrypted with the existing Fernet encryption manager.

4. SemanticMemory
- SQLite-backed embedding memory using existing local embedding model.
- Stores embedding vectors and metadata for similarity retrieval.

## Data Flow

1. User sends a message.
2. BrainController stores the user role message.
3. SmartRouter/agents/LLM generate assistant response.
4. BrainController stores assistant role message.
5. BrainController stores full interaction in conversation_interactions.
6. Automatic learning heuristics detect facts/preferences from user text.
7. Important facts are written to LongTermMemory and indexed in SemanticMemory.
8. On each new question, BrainController builds context from:
   - recent conversation
   - semantic memory search results
   - long-term memory entries
9. Combined context is injected into the system prompt before LLM generation.

## Importance Ranking

Importance is scored from 1 to 10.

- High (8-10): user preferences and personal profile facts.
- Medium (5-7): project goals and stable contextual facts.
- Low (1-4): temporary or short-lived details.

Low-importance entries can be removed by cleanup policy.

## Cleanup

Scheduled cleanup runs in background via MemoryCleanupScheduler.

- Default interval: every 24 hours.
- Removes low-importance memories older than configured threshold.

## API Endpoints

Base endpoints:

- GET /memory/history
  - Returns conversation interaction history.
  - Supports user_id, session_id, and limit.

- GET /memory/search
  - Returns semantic and long-term matches for a query.

- DELETE /memory/{id}
  - Deletes one long-term memory entry for the active user.

## Logging

Memory events are written to:

- data/logs/memory.log

Events logged:

- memory stored
- memory retrieved
- memory deleted

## Integration Points

- BrainController uses MemoryManager as the central memory orchestrator.
- MemoryManager composes ConversationMemoryStore, LongTermMemory, SemanticMemory, and ShortTermMemory.
- Existing encryption manager is used for sensitive long-term memory values.

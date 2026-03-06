# Model Consolidation Plan

## Goal

Retire legacy ORM path (`app/models/*` + `app/memory/memory_manager.py`) and standardize on:

- `app/database/models.py`
- `app/memory/memory_service.py`
- `app/memory/personalization.py`

## Current Risks

- Two model trees define overlapping concepts (`Conversation`, `Memory`, `User`).
- Two Base import paths existed (`app.database.db.Base` and `app.database.base.Base`).
- Different services write/read different tables, causing silent data drift.

## Target Architecture

One ORM Base, one table set, one service layer:

1. ORM base: `app.database.db.Base` only.
2. Domain tables: `app.database.models` (+ `app.models.user` if kept temporarily).
3. Memory APIs: `MemoryService` and `ConversationManager` using `app.database.models`.

## Migration Steps

1. Freeze writes to legacy memory path.
2. Add an adapter in `memory_manager.py` that forwards all operations to `MemoryService`.
3. Replace imports of `app.models.memory`, `app.models.conversation`, `app.models.contact` with `app.database.models`.
4. Add one DB migration script for legacy table data copy (if tables exist in production).
5. Remove dead files after two clean releases:
   - `app/models/memory.py`
   - `app/models/conversation.py`
   - `app/models/contact.py`
   - legacy code in `memory_manager.py`

## Done Definition

- `rg "from app.models.(memory|conversation|contact)"` returns no code-path usage.
- All memory/chat tests pass using only `MemoryService`.
- Startup creates one coherent schema without compatibility patches.

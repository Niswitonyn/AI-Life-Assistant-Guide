# Reasoning Engine

## Goal

Improve interpretation of ambiguous/complex user messages beyond keyword routing:

- decide intent and whether automation should run
- choose an agent category (browser/system/file/email/document)
- resolve follow-ups using conversation context (e.g. “download those images”)
- ask clarifying questions when confidence is low

## Module

- `backend/app/core/reasoning_engine.py`

### Output schema

`ReasoningEngine.analyze_intent(user_input, context)` returns:

```json
{
  "intent": "browser_action",
  "agent": "browser_agent",
  "confidence": 0.78,
  "should_execute": true,
  "rewritten": "download images of cats",
  "clarification": null
}
```

## How it works

1. **Heuristics first** for speed/reliability (no network):
   - detects common Q&A vs automation
   - resolves follow-ups using recent conversation context
2. **Optional LLM classification** if an AI provider is configured:
   - model returns JSON classification
   - protected by a strict schema + confidence threshold
3. **Rewriting approach**
   - the engine outputs a `rewritten` command string
   - BrainController routes that string through SmartRouter + TaskPlanner
   - SecurityManager still validates every task before execution

## Integration

- `backend/app/core/brain_controller.py`
  - runs SmartRouter normally
  - if no tasks are detected, runs ReasoningEngine
  - if confident and `should_execute=true`, executes the rewritten plan
  - otherwise asks clarification or falls back to chat

## Logging

- `backend/app/core/reasoning_logs.py`
  - writes JSON events to:
    - `backend/data/logs/reasoning.log`
    - `backend/logs/reasoning.log` (compat)

## Learning / stats

- `backend/app/core/usage_stats.py`
  - stores simple local counts in `backend/data/usage_stats.json`


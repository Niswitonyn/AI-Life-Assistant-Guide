# Self-Learning Behavior System

## Goal

Jarvis learns from user behavior to personalize actions and suggestions:

- frequently opened apps
- repeated web searches
- common folders / file actions
- preferences (like enabling/disabling tracking)

## Data Model (SQLite)

### `user_behavior`

Stored in `backend/data/database/assistant.db`:

- `user_id`
- `action` (e.g. `open_app:chrome`, `web_search:ai news`)
- `frequency`
- `last_used`
- `context` (small JSON blob)

### `user_preferences`

- `user_id`
- `key`
- `value`
- `updated_at`

Key used by default:

- `behavior_tracking_enabled` (`true|false`)

## Tracking

- `TaskExecutor` records successful task actions into `user_behavior`.
  - Apps: `open_app:<app>`
  - Searches: `web_search:<query>`
  - Folders: `open_folder`

Files:

- `backend/app/learning/behavior_tracker.py`
- `backend/app/core/task_executor.py`

## Suggestions

- `SuggestionEngine` emits `suggestion.new` events on common milestones (5/10/25 uses).
- The Electron GUI listens over `/api/events/ws` and shows toast notifications.

Files:

- `backend/app/learning/suggestion_engine.py`
- `frontend/src/components/Notifications.jsx`

## Privacy Controls

Users can:

- disable behavior tracking
- reset learning data (behavior + preferences)

Backend API:

- `POST /api/learning/tracking`
- `POST /api/learning/reset`

Frontend:

- `frontend/src/components/SettingsPanel.jsx`

## Reasoning Integration

`ReasoningEngine` receives a lightweight behavior summary (e.g. most used app) so it can resolve ambiguous commands like:

- “open browser” -> opens the most used browser/app

Files:

- `backend/app/core/brain_controller.py`
- `backend/app/core/reasoning_engine.py`

## Logging

Learning events are logged to:

- `backend/data/logs/learning.log`
- `backend/logs/learning.log` (compat)


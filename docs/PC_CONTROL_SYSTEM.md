# PC Control System (Windows)

## Overview

This project implements a reliable, safety-scoped PC Control System that allows the assistant to execute operating system tasks on Windows.

Execution flow:

`Chat / Voice` -> `BrainController` -> `SmartRouter` -> `TaskPlanner` -> (`SystemAgent` / `FileAgent`) -> Services -> Structured result

The frontend API contract remains unchanged: `POST /api/ai/chat` still returns:

```json
{ "response": "..." }
```

Internally, the agents return structured JSON payloads.

## Key Modules

- `backend/app/services/system_control.py`
  - Safe system operations (open apps, volume keys, shutdown/restart/lock, open folders)
  - Uses an `app_map` for known applications

- `backend/app/services/file_system_service.py`
  - Safe file operations (search/open/create/delete/list)
  - Enforces an allowlist of directories

- `backend/app/agents/system_agent.py`
  - Agent wrapper around `SystemControl`
  - Returns structured results and logs actions

- `backend/app/agents/file_agent.py`
  - Agent wrapper around `FileSystemService`
  - Returns structured results and logs actions

- `backend/app/core/system_logs.py`
  - Writes structured JSON logs to `backend/data/logs/system_actions.log` (also `backend/logs/system_actions.log` for compatibility)

## Supported Commands

System commands:

- `open chrome`
- `open vscode`
- `shutdown computer`
- `restart computer`
- `lock screen`
- `set volume 35`
- `increase volume`
- `decrease volume`
- `mute volume`

File system commands:

- `find file <name>`
- `open file <name>`
- `create folder <name>`
- `delete file <name>` (files only; refuses directory deletes; uses Recycle Bin on Windows)
- `open documents`
- `open downloads`

Compound commands are supported via `TaskPlanner`, e.g.:

`open documents and find file project report`

## Security Protections

File system restrictions:

- Only operates inside allowed directories:
  - `Documents`, `Downloads`, `Desktop`
  - the project workspace (repo root)
- Deleting directories is refused by default.
- "Open file" and "delete file" resolve a filename by searching only within allowed roots (with a short time limit).
- "Delete file" uses the Windows Recycle Bin when available (undoable), rather than a permanent delete.

System restrictions:

- Application launching uses `app_map` for known apps (no arbitrary command execution).
- No generic "run arbitrary command" API is exposed through SmartRouter.
- "Set volume" is best-effort (approximate) because it uses media keys.

## Logging

System + file actions are logged as JSON events to:

- `backend/data/logs/system_actions.log`
- `backend/logs/system_actions.log`

Fields include:
- command/action
- result status
- errors (if any)

## Extending `app_map`

Default mapping lives in `SystemControl.default_app_map()`:

- `chrome`
- `vscode`
- `notepad`
- `calculator`

Add new apps by extending the mapping or providing a custom map when constructing `SystemControl`.

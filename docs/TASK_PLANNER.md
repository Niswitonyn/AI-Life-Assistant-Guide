# Task Planner System

## Goal

Turn complex natural language commands into a safe, ordered, executable plan:

Example:

`open chrome and search cats then download images`

Becomes a sequence of tasks executed sequentially with progress updates.

## Components

### 1) TaskPlanner (splitting)

- File: `backend/app/core/task_planner.py`
- Responsibility: split a user command into **clauses** using connector words:
  - `and`, `then`, `after`, `next`, `;`, `,`
- Output: ordered list of clause strings.

### 2) SmartRouter (parsing + dependencies)

- File: `backend/app/router/smart_router.py`
- Responsibility:
  - parse each clause into `{action, params, agent}`
  - insert lightweight prerequisites when missing

Example dependency:

- `browser_search` / `browser_download_images` -> ensures a browser open step is present (either `browser_open` or `open_application chrome`)

### 3) TaskExecutor (execution engine)

- File: `backend/app/core/task_executor.py`
- Responsibility:
  - execute tasks sequentially
  - publish progress events:
    - `task_started`
    - `task_completed`
    - `task_failed` (and legacy `task_error`)
  - stop on first failure and return a **partial** result
  - call SecurityManager before every task (auth + confirmation + path restrictions)

### 4) BrainController (orchestration)

- File: `backend/app/core/brain_controller.py`
- Responsibility:
  - accept chat/voice input
  - call `SmartRouter.route()`
  - run `TaskExecutor.execute_tasks()`
  - aggregate task results into a single assistant response

## Error Recovery

If a task fails, execution stops and the assistant returns:

- completed tasks so far
- the failed task + error reason

## Security

Before each task executes, SecurityManager validates:

- permission level (SAFE/SENSITIVE/CRITICAL)
- authentication requirement for sensitive/critical
- confirmation requirement for sensitive/critical
- file/folder path restrictions (defense in depth)
- basic injection markers in raw command text

See `docs/SECURITY_SYSTEM.md` for details.


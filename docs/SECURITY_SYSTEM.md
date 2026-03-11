# Security System

## Goals

Because Jarvis can control the computer, the backend enforces a **Security + Permission System** to prevent:

- dangerous system operations
- unauthorized file access
- command injection / arbitrary command execution
- unsafe automation tasks
- sensitive data leaks

## Core Components

### 1) SecurityManager

- File: `backend/app/security/security_manager.py`
- Purpose: validate tasks before execution and classify permission level:
  - `SAFE` (default)
  - `SENSITIVE` (requires auth + confirmation)
  - `CRITICAL` (requires auth + confirmation)

Examples:

- SAFE: `open_application`, `open_folder`, `volume_control`
- SENSITIVE: `create_folder`, `delete_file`, `send_email`
- CRITICAL: `shutdown`, `restart`

The validator also applies defense-in-depth path checks for file/folder actions.

### 2) ConfirmationService

- File: `backend/app/security/confirmation_service.py`
- Stores pending sensitive/critical tasks per user for a short TTL.
- User must reply with `yes/confirm/go ahead` to execute or `no/cancel` to abort.

### 3) Enforcement in BrainController

- File: `backend/app/core/brain_controller.py`
- Before dispatching any task, the controller calls `SecurityManager.validate_task(...)`.
- If confirmation is required, it returns `status="needs_confirmation"` with a prompt.
- If blocked, it returns an error explaining the restriction.

### 4) Rate Limiting

- File: `backend/app/main.py`
- Adds a small in-memory rate limiter to reduce abuse on key endpoints:
  - `/api/ai/chat`
  - `/api/voice/input` and `/voice/input`
  - `/api/documents/upload` and `/documents/upload`

### 5) Security Logging

- File: `backend/app/security/security_logs.py`
- Writes JSON-line security events to:
  - `backend/data/logs/security.log`
  - `backend/logs/security.log` (compat)

Events include:

- blocked tasks
- confirmation requirements
- rate limiting
- temporary blocks (abuse threshold)

## File Access Restrictions

Allowed roots (enforced by both services and SecurityManager):

- `Documents`
- `Downloads`
- `Desktop`
- user workspace (project root)

Blocked roots:

- `C:\\Windows`
- `C:\\Program Files`
- `C:\\Program Files (x86)`

## Abuse Protection

Repeated unsafe requests within a short window trigger a temporary block (defaults can be tuned via env):

- `SECURITY_BLOCK_THRESHOLD` (default 6)
- `SECURITY_TEMP_BLOCK_S` (default 300s)


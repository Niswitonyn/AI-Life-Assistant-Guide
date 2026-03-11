# Gmail Automation System

## Overview

Gmail automation is implemented as a structured, BrainController-driven workflow that supports:

- `open gmail`
- `read my emails`
- `search emails from <person>`
- `write email to <person> about <topic>`
- `improve this email`
- `notify when new mail arrives`
- `track emails from <specific sender>`

Flow:

`Chat / Voice` → `BrainController` → `SmartRouter` → `TaskPlanner` → `GmailAgent` → (optional) EmailMonitor/Notifier

The frontend API contract remains unchanged: `POST /api/ai/chat` returns:

```json
{ "response": "..." }
```

Internally, tasks return structured JSON results.

## Key Modules

- `backend/app/agents/gmail_agent.py`
  - Structured Gmail agent actions:
    - `read_inbox`
    - `search_email`
    - `send_email` (confirmation-based)
    - `draft_email` (AI-generated + confirmation-based)
    - `improve_email`
    - `track_sender`
    - `get_latest_email`

- `backend/app/services/email_ai_service.py`
  - Uses the same AI provider selected by chat (`provider_factory`)
  - Features:
    - improve email drafts
    - summarize emails
    - generate replies
    - generate subject/body drafts

- `backend/app/services/email_monitor.py`
  - Polls inbox periodically (default 60 seconds) to detect new mail for tracked senders
  - Triggers notifications via `EmailNotifier`

- `backend/app/notifications/email_notifier.py`
  - Emits:
    - voice notifications (if voice assistant is available)
    - event bus messages (`email.new`)

- `backend/app/services/event_bus.py` + `backend/app/api/routes_events.py`
  - Simple server-side event system
  - SSE endpoint: `GET /api/events/stream`

## Confirmation Workflow (Draft + Send)

Actions `draft_email` and `send_email` return a “ready to send” preview and require explicit confirmation:

- User says: `yes send it` → BrainController confirms and sends
- User says: `cancel` → cancels pending send

## Tracking + Inbox Monitoring

Commands:

- `track emails from boss@gmail.com`
- `notify when new mail arrives` (tracks `*` wildcard)

Tracked senders are stored in SQLite table `tracked_senders`.

Monitoring:

- Runs in-process on backend startup (FastAPI lifespan)
- Interval configured by env var:
  - `EMAIL_MONITOR_INTERVAL_SECONDS` (default: 60)

## Security Model

- OAuth tokens are stored encrypted (no plaintext token files)
  - Storage handled by `backend/app/services/google_token_store.py`
- Sending is rate-limited (basic per-process limit)
- Recipient email validation is enforced

## Logging

- Email automation events are logged to:
  - `backend/data/logs/email.log`

Events include:
- email read/search
- draft generated
- email sent
- notifications


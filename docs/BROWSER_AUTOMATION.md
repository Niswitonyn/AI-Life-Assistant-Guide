# Browser Automation (Playwright)

## Overview

This project uses a unified Browser Automation System to reliably execute multi-step commands like:

- `open chrome and search cats and download cat images`
- `open website https://example.com and collect information about it`

The system is designed to work through the same backend execution path as chat and voice:

`Chat / Voice` → `BrainController` → `SmartRouter` → `TaskPlanner` → `BrowserAgent` → `BrowserAutomation (Playwright)`

## Key Modules

- `backend/app/services/browser_automation.py`
  - Persistent Playwright session (browser/context/page)
  - Safe navigation (http/https only)
  - Google search result extraction
  - Page extraction helpers (titles/paragraphs/links)
  - Image downloads to `backend/data/downloads/images/`

- `backend/app/agents/browser_agent.py`
  - Single unified agent entrypoint for browser tasks
  - Returns structured results in the format:
    ```json
    {
      "status": "success",
      "agent": "browser_agent",
      "action": "browser_search",
      "data": { "...": "..." }
    }
    ```

- `backend/app/core/task_planner.py`
  - Splits compound commands into task clauses

- `backend/app/router/smart_router.py`
  - Parses each clause into an action + params mapped to `browser_agent`

- `backend/app/core/browser_logs.py`
  - Structured JSON logs for browser automation commands (timing, download count, errors)

## Supported Commands

These phrases are recognized by `SmartRouter` and mapped to browser actions:

- `open chrome`
  - Action: `browser_open`

- `search <query>`
  - Action: `browser_search`

- `download images of <query>`
  - Action: `browser_download_images`

- `download <query> images`
  - Action: `browser_download_images`

- `open website <url>` / `open site <url>`
  - Action: `browser_visit`

- `collect information about <topic>`
  - Action: `browser_collect_info`

## Multi-step Execution

Example input:

`open chrome and search cats and download cat images`

Typical planned tasks (conceptually):

```json
[
  { "action": "browser_open" },
  { "action": "browser_search", "params": { "query": "cats" } },
  { "action": "browser_download_images", "params": { "query": "cats", "limit": 10 } }
]
```

Task chaining:
- If a later task omits a query (e.g. `download images`), `BrainController` fills it from the previous `search` query.

## Data Extraction

`BrowserAutomation` provides:
- `extract_titles()`
- `extract_paragraphs()`
- `extract_links()`

`browser_collect_info` performs:
1. Google search for the topic
2. Opens the first result
3. Extracts titles/paragraphs/links

## Image Downloads

Images are saved to:

- `backend/data/downloads/images/`

Filename format:

- `query_timestamp_index.jpg`

Returned metadata example:

```json
{
  "downloaded": 10,
  "path": "…/backend/data/downloads/images",
  "files": ["…jpg", "…jpg"]
}
```

## Security Controls

- Only `http://` and `https://` URLs are allowed (`file://`, `javascript:`, etc. blocked).
- No task-exposed “run JS” capability.
- Downloads restricted to `backend/data/downloads/*`.
- Playwright timeouts applied for navigation/actions.

## Performance Notes

- Browser session is reused across requests while the backend process is running.
- Image downloads run concurrently with a fixed concurrency limit.

## Setup (Playwright)

Install Python dependency:

```bash
pip install playwright
```

Install browser binaries:

```bash
playwright install chromium
```

Optional:
- Set `PLAYWRIGHT_BROWSER_CHANNEL=chrome` to force using system Chrome when available.
- Set `BROWSER_HEADLESS=false` to see the browser UI.


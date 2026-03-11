# System Monitoring & Health Management

This project includes a lightweight monitoring subsystem that continuously checks key backend components, records performance metrics, and reports health to the Electron/React frontend via the existing event stream.

## Overview

**Core goals**
- Detect module failures early (DB, RAG store, voice/TTS, imports)
- Attempt safe automatic recovery for supported components
- Track basic performance metrics (CPU/RAM, API latency, task duration)
- Publish health + alerts to the UI without blocking normal operation

## Backend Architecture

**Modules**
- `backend/app/monitoring/health_monitor.py`: periodic health checks (default every 30s), recovery attempts, publishes `health.update`
- `backend/app/monitoring/performance_metrics.py`: in-memory metrics aggregator (CPU/RAM best-effort, API latency, task duration)
- `backend/app/monitoring/alert_manager.py`: alert dedupe/throttle, publishes `alert.new`
- `backend/app/monitoring/status_registry.py`: thread-safe latest snapshot + recent alerts
- `backend/app/monitoring/monitor_logs.py`: writes `system_monitor.log`

**Startup integration**
- The monitor starts/stops via FastAPI lifespan in `backend/app/main.py`.

## Health Checks

Health snapshots look like:
```json
{
  "status": "healthy|degraded|unhealthy",
  "checked_at": 1710000000.0,
  "components": { "database": { "status": "connected" }, "rag_vector_store": { "status": "running" } },
  "metrics": { "process": { "cpu_percent": 12.3, "rss_mb": 420.0 } },
  "throttled": false,
  "alerts": []
}
```

**Components monitored**
- Database connectivity (`SELECT 1`)
- RAG vector store (file-backed store health + reload)
- Voice TTS worker (best-effort health + reset)
- Import checks (BrainController, ReasoningEngine, TaskPlanner/Executor, key agents)

**Status rules**
- `unhealthy`: a critical component failed (currently: `database`, `rag_vector_store`)
- `degraded`: a non-critical component failed (ex: `voice_tts`), or imports fail
- `healthy`: all checks passing

## Automatic Recovery

Supported recoveries (best-effort, retry-limited)
- Database: `init_db()` then re-check
- RAG store: `vector_store.reload()` then re-check
- Voice TTS: `text_to_speech.reset_tts()` then re-check

Recovery attempts are capped and use a cooldown to avoid loops. Each attempt is logged to `system_monitor.log`.

## Performance Metrics

**Tracked**
- Process CPU% (sampled between checks, best-effort on Windows)
- Process RSS memory (Working Set, best-effort on Windows)
- API latency (FastAPI middleware buckets by prefix)
- Task execution time per action (recorded in `TaskExecutor`)

## API

**Health endpoint**
- `GET /system/health`
- `GET /api/system/health`

Returns the latest snapshot from the status registry plus recent alerts.

**Safe restart endpoint (auth required)**
- `POST /api/system/restart`
  - body: `{ "component": "database|rag_vector_store|voice_tts" }`

## Frontend Integration

The frontend listens for:
- `health.update` (updates the status badge + CPU/RAM line)
- `alert.new` (shown as a toast, also appears in the status feed)

Fallback polling is enabled in `frontend/src/components/SystemStatus.jsx` (every 15s) using `GET /api/system/health`.

## Logging

Monitor logs are written to:
- `logs/system_monitor.log` (portable-aware via `AI_LIFE_LOG_DIR`)
- legacy fallback: `backend/logs/system_monitor.log`

Alerts are also emitted to the event stream as `alert.new`.


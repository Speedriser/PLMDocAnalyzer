# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PLM Digitizer is a document intelligence platform that converts unstructured documents (PDF, DOCX, XLSX, images, CSV/TXT) into structured data for PLM system import. It uses FastAPI with async/background processing, LLM-powered field extraction, and real-time WebSocket progress streaming.

## Commands

```bash
# Install dependencies
pip install -r plm_digitizer/requirements.txt

# Run the application (starts on http://localhost:8000)
cd plm_digitizer && python main.py

# The frontend SPA is served at http://localhost:8000 (no build step needed)
```

There is no test suite, lint config, Makefile, or Docker setup in this project.

## Architecture

### Entry Points
- `plm_digitizer/main.py` — FastAPI app, lifespan hook (DB init + Celery start), WebSocket handler, global exception handler
- `plm_digitizer/static/app.html` — Single-file SPA (~2600 lines, Alpine.js + Tailwind CSS + Chart.js, no build step)

### 5-Stage Processing Pipeline

Runs in `services/worker.py` via Celery (or ThreadPoolExecutor fallback if Redis is unavailable):

1. **File Discovery** (`services/file_discovery.py`) — async recursive directory walk returning `FileMetadata` objects
2. **Text Extraction** (`services/extractor.py`) — per-format extraction; PDFs use pdfplumber with pytesseract OCR fallback; images use pytesseract + PIL preprocessing
3. **LLM Extraction** (`services/llm_agent.py`) — batches 1–5 documents per API call; routes to OpenAI / Azure OpenAI / Ollama based on model prefix; returns JSON with confidence scores
4. **Output Writing** (`services/output_writer.py`) — factory pattern returning `ExcelWriter` or `CSVWriter`; Excel is color-coded by confidence (green ≥0.8, yellow 0.5–0.8, red <0.5)
5. **PLM Push** (`services/aras_push.py`, optional) — Aras Innovator REST/OData integration

### Key Files

| File | Purpose |
|------|---------|
| `config.py` | Settings, encryption (machine-specific Fernet key), supported file types, LLM model registry |
| `database.py` | SQLAlchemy ORM models: `Run`, `RunLog`, `FileResult`, `PLMConnection`, `Setting`, `AuditLog`, `Preset` |
| `models.py` | Pydantic request/response schemas |
| `routers/runs.py` | Run CRUD, logs, results, dashboard stats |
| `routers/settings.py` | API key/password management with masking |
| `routers/files.py` | Folder scan and LLM/Aras connection validation |
| `routers/push.py` | PLM connection management |

### WebSocket Architecture

`/ws/runs/{id}` uses an asyncio Queue to decouple background worker threads from the async WebSocket handler. Callbacks are registered/unregistered per run. Heartbeat ping every 5 seconds; auto-closes on completion.

### Encryption

API keys, passwords, and secrets are encrypted with a machine-specific Fernet key (derived from hostname + machine ID) before storage in the `Setting` table (`is_encrypted=True`). They are never logged and are masked in API responses (first/last 4 chars + asterisks). Encrypted values are **not portable** across machines.

### Graceful Degradation

The app checks Redis availability at startup and sets `config.USE_REDIS`. If Redis is unavailable, Celery tasks fall back to `ThreadPoolExecutor`. Thread-safe global dicts (`_cancel_flags`, `_ws_connections`) are protected by `threading.Lock`.

## Environment Variables

| Variable | Default |
|----------|---------|
| `DATABASE_URL` | `sqlite:///data/plm_digitizer.db` |
| `REDIS_URL` | `redis://localhost:6379/0` |

All other configuration (LLM provider keys, processing parameters) is managed through the `/api/settings` endpoint and stored encrypted in the database.

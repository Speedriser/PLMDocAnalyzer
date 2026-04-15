# PLMDocAnalyzer

**PLM Digitizer** — a document intelligence platform that turns unstructured
engineering documents (PDFs, scanned images, Word, Excel, CSV/TXT) into
structured data ready for import into Product Lifecycle Management (PLM)
systems such as Aras Innovator.

The application is a self-contained FastAPI service with a single-file Alpine.js
SPA frontend, a 5-stage async processing pipeline, an LLM-powered field
extraction engine (OpenAI / Azure OpenAI / Ollama), and an optional Aras REST
push integration.

> The detailed developer guide lives at
> [`PLMDocAnalyzer/plm_digitizer/README.md`](PLMDocAnalyzer/plm_digitizer/README.md).
> This top-level README is the project-wide overview.

---

## What it does

Point it at a folder of mixed engineering documents and it will:

1. **Walk the folder tree** and identify every supported file
   (`.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.png`, `.jpg`, `.jpeg`,
   `.tiff`, `.bmp`, `.csv`, `.txt`).
2. **Extract text** from each file using the best method for its type
   (pdfplumber for text PDFs, Tesseract OCR fallback for scanned PDFs and
   images, python-docx for DOCX, openpyxl for XLSX, csv.Sniffer for CSV).
3. **Send batched documents to an LLM** (1–5 files per request) with a
   system prompt that asks for the caller's chosen fields (e.g. *Part
   Number, Revision, Description, Material, Weight*) as strict JSON. The
   model also returns a `_confidence` score and a `_source_hint` per doc.
4. **Write a color-coded output file** — Excel (green ≥ 0.8, yellow
   0.5–0.8, red < 0.5 confidence) or CSV — streamed as batches complete.
5. **Optionally push records to Aras Innovator** over REST/OData with
   AI-assisted column-to-property mapping.

Progress, logs, and per-file results stream to the browser over a WebSocket
(`/ws/runs/{id}`) in real time, with ETA, throughput, token usage, and
estimated cost.

---

## Repository layout

```
PLMDocAnalyzer/
├── README.md                    ← you are here
└── PLMDocAnalyzer/
    ├── CLAUDE.md                ← guidance for Claude Code sessions
    ├── README.md                ← short stub
    ├── sample_File/             ← sample invoice PDF + image for demos
    └── plm_digitizer/           ← the actual Python application
        ├── main.py              ← FastAPI app, lifespan, WebSocket, /api/health
        ├── config.py            ← settings, Fernet encryption, LLM model registry
        ├── database.py          ← SQLAlchemy models (Run, RunLog, FileResult, …)
        ├── models.py            ← Pydantic request/response schemas
        ├── requirements.txt
        ├── README.md            ← detailed developer guide (architecture, API)
        ├── routers/
        │   ├── runs.py          ← run CRUD, logs, results, dashboard stats
        │   ├── settings.py      ← encrypted key/password storage (masked on read)
        │   ├── files.py         ← folder scan, OpenAI/Aras validation
        │   └── push.py          ← PLM connections & push lifecycle
        ├── services/
        │   ├── file_discovery.py← async recursive walker → FileMetadata
        │   ├── extractor.py     ← per-format text extraction with OCR fallback
        │   ├── llm_agent.py     ← OpenAI/Azure/Ollama batch extraction + retry
        │   ├── output_writer.py ← Excel (color-coded) & CSV writers (factory)
        │   ├── aras_push.py     ← Aras Innovator REST/OData push
        │   └── worker.py        ← 5-stage pipeline, Celery + thread-pool fallback
        ├── static/
        │   └── app.html         ← single-file SPA (Alpine + Tailwind + Chart.js)
        └── data/                ← SQLite DB, rotating logs, output files (auto)
```

---

## Architecture at a glance

```
┌─────────────────────────────────────────────────────────┐
│   Browser SPA  (static/app.html — Alpine + Tailwind)    │
└──────────────┬──────────────────────────────────────────┘
               │ HTTP + WebSocket
┌──────────────▼──────────────────────────────────────────┐
│                 FastAPI (main.py)                       │
│  routers/settings  routers/runs  routers/files  push    │
│           /ws/runs/{id}   /api/health   /api/docs       │
└──────────────┬──────────────────────────────────────────┘
               │ process_run_task / push_to_plm_task
┌──────────────▼──────────────────────────────────────────┐
│     services/worker.py   (Celery if Redis, else         │
│                           ThreadPoolExecutor fallback)  │
│                                                         │
│  1. File Discovery   services/file_discovery.py         │
│  2. Text Extraction  services/extractor.py              │
│       PDF → pdfplumber → pytesseract (OCR fallback)     │
│       DOCX/XLSX/Image/CSV/TXT → dedicated extractors    │
│  3. LLM Extraction   services/llm_agent.py              │
│       batches 1–5 docs → OpenAI / Azure / Ollama        │
│       returns JSON + _confidence + _source_hint         │
│  4. Output Writing   services/output_writer.py          │
│       Excel (color-coded by confidence) or CSV stream   │
│  5. PLM Push (opt.)  services/aras_push.py              │
│       Aras Innovator REST/OData, batched + progress CB  │
└──────┬──────────────────────────────────────────┬───────┘
       │                                          │
┌──────▼───────────────┐                  ┌───────▼────────┐
│ SQLite (SQLAlchemy)  │                  │ Redis (optional)│
│ Run, RunLog,         │                  │ Celery broker   │
│ FileResult, Setting, │                  │ + result backend│
│ PLMConnection,       │                  └─────────────────┘
│ AuditLog, Preset     │
└──────────────────────┘
```

### Key design choices

- **Graceful degradation** — `config.USE_REDIS` is probed at startup. If
  Redis is unreachable, Celery is skipped entirely and runs execute on an
  in-process `ThreadPoolExecutor`. No external dependencies are required
  to get started.
- **Streaming output** — `openpyxl` write-only mode and `csv.writer`
  allow the output file to grow row-by-row as batches complete, so even
  multi-million-file runs do not blow up memory.
- **Per-machine Fernet encryption** — API keys, Aras passwords, and
  secrets are encrypted at rest with a Fernet key derived from
  `hostname + machine + PID`. Values are masked in API responses
  (`first4…last4`). Encrypted values are **not portable** across machines.
- **Thread-safe broadcast** — A global `_ws_connections` dict (protected
  by a lock) maps each `run_id` to a list of WebSocket callbacks. Worker
  threads call `broadcast_event(run_id, …)`; the WebSocket handler drains
  an `asyncio.Queue` so thread context and async context stay separated.
- **Cancellation** — `request_cancel(run_id)` flips a flag that the
  worker checks between files; cancelled runs are marked `cancelled` in
  the DB and the WebSocket sends a final `completed`/`error` event
  before closing.
- **Multi-provider LLM routing** — `services/llm_agent.py` inspects the
  `llm_provider` setting (`openai` | `azure` | `ollama`) and wires up
  the correct OpenAI-compatible client, with retry + friendly error
  translation (`401 → "key invalid"`, `429 → "rate limit, will retry"`,
  etc.). Azure deployment names are user-configurable.

---

## Supported file types & extraction

| Format            | Method                                      |
|-------------------|---------------------------------------------|
| PDF (searchable)  | `pdfplumber` — text + tables                |
| PDF (scanned)     | `pdf2image` + `pytesseract` OCR fallback    |
| DOCX              | `python-docx` — paragraphs + tables         |
| XLSX / XLS        | `openpyxl` — all sheets                     |
| PNG / JPG / JPEG  | `pytesseract` with PIL preprocessing        |
| TIFF / BMP        | `pytesseract` with PIL preprocessing        |
| CSV               | `csv.Sniffer` + `csv.reader`                |
| TXT               | Direct read with encoding detection         |

Any file < 100 MB in size and with a supported extension is picked up by
the async walker; hidden files, Office lock files (`~$…`), `.DS_Store`,
`Thumbs.db`, and `desktop.ini` are skipped automatically.

---

## LLM providers

Configured in `plm_digitizer/config.py` (`LLM_MODELS`) and selected in the
UI via **Settings → LLM**.

- **OpenAI** — `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`
- **Azure OpenAI** — user-supplied endpoint, API version, and deployment
  name (defaults: `2024-10-21`, deployment name matches model)
- **Ollama (local)** — `qwen2.5:7b/14b/32b`, `qwen2.5-coder:7b`,
  `llama3.1:8b`, `llama3.2:3b`, `mistral:7b` via Ollama's
  OpenAI-compatible API at `http://localhost:11434`

---

## Data model (SQLite via SQLAlchemy)

| Table             | Purpose                                                        |
|-------------------|----------------------------------------------------------------|
| `runs`            | One row per processing run — status, counts, tokens, cost      |
| `run_logs`        | Time-ordered log lines per run (info / warning / error)        |
| `file_results`    | Per-file outcome — extracted JSON, confidence, error, timing   |
| `settings`        | Key-value store; sensitive rows flagged `is_encrypted=True`    |
| `plm_connections` | Aras connections — URL, DB, user, encrypted password           |
| `audit_logs`      | Action history (`run_created`, etc.)                           |
| `presets`         | Saved run configurations                                       |

---

## HTTP & WebSocket API

| Method | Path                              | Description                          |
|--------|-----------------------------------|--------------------------------------|
| GET    | `/`                               | Serve the SPA                        |
| GET    | `/api/health`                     | Health (Redis + DB probe)            |
| GET    | `/api/docs` / `/api/redoc`        | Auto-generated OpenAPI docs          |
| GET/POST | `/api/settings`                 | Read (masked) / write encrypted keys |
| POST   | `/api/validate/openai`            | Validate OpenAI key                  |
| POST   | `/api/validate/folder`            | Scan folder, return file breakdown   |
| POST   | `/api/validate/aras`              | Test Aras connection                 |
| GET/POST | `/api/runs`                     | List / create a run                  |
| GET/DELETE | `/api/runs/{id}`              | Get / cancel a run                   |
| GET    | `/api/runs/{id}/logs`             | Paginated logs                       |
| GET/PATCH | `/api/runs/{id}/results[/{rid}]` | Paginated results / manual edit   |
| GET    | `/api/runs/{id}/download`         | Download the generated output file   |
| POST   | `/api/runs/{id}/push`             | Push to Aras                         |
| GET    | `/api/runs/{id}/push/status`      | Push progress                        |
| GET    | `/api/dashboard/stats`            | Aggregate KPIs + recent activity     |
| POST/GET/DELETE | `/api/connections[/{id}]` | Manage Aras connections              |
| POST   | `/api/connections/{id}/test`      | Test an Aras connection              |
| WS     | `/ws/runs/{id}`                   | Live `state` / `log` / `progress` / `completed` / `ping` events |

---

## Running it locally

Prereqs: **Python 3.11+**, plus **Tesseract OCR** and **Poppler** on PATH if
you expect to process scanned PDFs or images. Redis is optional — the app
falls back to a thread pool when it isn't present.

```bash
cd PLMDocAnalyzer/plm_digitizer
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py                                       # http://localhost:8000
```

First-time setup: open the UI, go to **Settings → LLM**, enter an OpenAI /
Azure key (or pick Ollama), click **Save** then **Validate Key**. Create a
new run from the sidebar; the **Live Execution View** streams progress.

### Environment variables

| Variable        | Default                                      |
|-----------------|----------------------------------------------|
| `DATABASE_URL`  | `sqlite:///data/plm_digitizer.db`            |
| `REDIS_URL`     | `redis://localhost:6379/0`                   |

Everything else (LLM keys, Azure endpoint/deployment, Ollama base URL,
Aras credentials, worker/batch counts, confidence threshold) is configured
through the UI and stored encrypted in the `settings` table.

---

## Security notes

- **Never logged, never exposed** — API keys and passwords are Fernet-
  encrypted on write, decrypted only in-memory at the moment of the API
  call, and always masked (`first4…last4`) in API responses.
- **Machine-bound encryption** — The Fernet key is derived from the host
  machine; database files copied to a different machine **cannot decrypt
  their stored secrets**. Re-enter credentials after a migration.
- **No authentication layer** — the app trusts anyone who can reach it on
  the network. Run it behind a reverse proxy with authn/authz if you need
  to expose it beyond localhost.
- **CORS** is wide-open (`allow_origins=["*"]`) to keep local development
  frictionless. Tighten this before deployment.

---

## Sample data

`PLMDocAnalyzer/sample_File/` contains a *Sample Vendor Invoice.pdf* and
an *invoice-luxury.png* you can point a run at to try the pipeline
end-to-end without bringing your own documents.

---

## Status

- There is no test suite, lint config, Makefile, or Docker setup yet.
- `fix3.py`, `svg_fix3.py`, `temp_check.js`, `temp_js.js`, and
  `test_azure.py` in `plm_digitizer/` are ad-hoc helper scripts kept
  alongside the application; they are not part of the runtime.

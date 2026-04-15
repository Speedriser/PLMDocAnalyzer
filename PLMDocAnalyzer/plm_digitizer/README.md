# PLM Digitizer — Document Intelligence Platform

Convert millions of unstructured documents (PDFs, images, Word, Excel, flat files)
into structured data ready for PLM system import.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                            │
│   Alpine.js + Tailwind CSS + Chart.js (single app.html file)   │
└────────────────────┬───────────────────────────────────────────┘
                     │ HTTP/WebSocket
┌────────────────────▼───────────────────────────────────────────┐
│                    FastAPI (main.py)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ /api/    │ │ /api/    │ │ /api/    │ │ /ws/runs/{id}   │  │
│  │ settings │ │ runs     │ │ connect. │ │  (WebSocket)    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
└────────────────────┬───────────────────────────────────────────┘
                     │
┌────────────────────▼───────────────────────────────────────────┐
│               Celery Worker (background thread)                 │
│                                                                 │
│  Stage 1: File Discovery (pathlib async walker)                │
│  Stage 2: Text Extraction (ThreadPoolExecutor)                 │
│    ├── PDF (pdfplumber → pytesseract fallback)                 │
│    ├── DOCX (python-docx)                                      │
│    ├── Excel (openpyxl)                                        │
│    ├── Images (pytesseract + PIL preprocessing)                │
│    └── CSV/TXT (csv.reader)                                    │
│  Stage 3: LLM Extraction (OpenAI batched calls)                │
│  Stage 4: Output Writing (Excel write-only / CSV stream)       │
│  Stage 5: PLM Push (Aras REST/OData)                          │
└────────────────────┬───────────────────────────────────────────┘
          ┌──────────┴──────────┐
┌─────────▼────────┐  ┌────────▼────────┐
│  SQLite Database │  │  Redis (Celery) │
│  (SQLAlchemy)    │  │  broker+backend │
└──────────────────┘  └─────────────────┘
```

---

## Prerequisites

- **Python 3.11+**
- **Redis** (for Celery task queue)
  - Windows: [download Redis](https://github.com/tporadowski/redis/releases)
  - Linux/Mac: `apt install redis-server` or `brew install redis`
- **Tesseract OCR** (for image/scanned PDF processing)
  - Windows: [download installer](https://github.com/UB-Mannheim/tesseract/wiki)
  - Linux: `apt install tesseract-ocr`
  - Mac: `brew install tesseract`
- **Poppler** (for pdf2image)
  - Windows: [download](https://github.com/oschwartz10612/poppler-windows/releases/)
  - Linux: `apt install poppler-utils`
  - Mac: `brew install poppler`

---

## Installation

```bash
# 1. Clone/copy the project
cd plm_digitizer

# 2. Create a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Redis (in a separate terminal)
redis-server

# 5. Run the application
python main.py
```

The app will be available at **http://localhost:8000**

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///data/plm_digitizer.db` | SQLAlchemy database URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |

### First-time Setup

1. Open http://localhost:8000
2. Go to **Settings → LLM Configuration**
3. Enter your OpenAI API key and click **Save**
4. Click **Validate Key** to confirm it works

---

## Usage

### Starting a Processing Run

1. Click **New Run** in the sidebar
2. **Step 1 — Source**: Enter the folder path containing your documents, click Scan
3. **Step 2 — Fields**: Define what data to extract (e.g., "Part Number, Description, Revision")
4. **Step 3 — Output**: Choose run name, format (Excel/CSV), and LLM model
5. **Step 4 — PLM Target**: Optionally configure Aras connection for direct push
6. **Step 5 — Review**: Verify settings, click **Launch Run** 🚀

### Monitoring Progress

After launch, the **Live Execution View** shows:
- Animated circular progress ring
- Real-time file processing stats
- Scrolling log stream (color-coded by severity)
- Recent files feed with pass/fail status

### Reviewing Results

In **Results Explorer**:
- Filter by All / Passed / Failed / Skipped
- Click any row to open the detail panel
- Edit incorrect extracted values inline
- Download selected results as CSV

### Pushing to Aras PLM

1. Go to **PLM Connections**, click **Add Connection**
2. Enter your Aras server URL, database, username, and password
3. Click **Test** to verify connectivity
4. On a completed run, click **Push to PLM**
5. Map output columns to Aras property names (AI-assisted)
6. Monitor push progress in real-time

---

## Supported File Types

| Format | Extraction Method |
|--------|------------------|
| PDF (searchable) | pdfplumber — text + tables |
| PDF (scanned) | pdf2image + pytesseract OCR |
| DOCX | python-docx — paragraphs + tables |
| XLSX / XLS | openpyxl — all sheets |
| PNG / JPG / JPEG | pytesseract with preprocessing |
| TIFF / BMP | pytesseract with preprocessing |
| CSV | csv.Sniffer + csv.reader |
| TXT | Direct read with encoding detection |

---

## Project Structure

```
plm_digitizer/
├── main.py              # FastAPI app, WebSocket endpoint, startup
├── config.py            # Settings, encryption, supported file types
├── database.py          # SQLAlchemy models (Run, FileResult, etc.)
├── models.py            # Pydantic request/response schemas
├── routers/
│   ├── settings.py      # GET/POST/DELETE /api/settings
│   ├── runs.py          # Full run CRUD, logs, results, dashboard
│   ├── files.py         # /api/validate/folder|openai|aras
│   └── push.py          # PLM connections + push operations
├── services/
│   ├── file_discovery.py# Async recursive directory walker
│   ├── extractor.py     # Per-file-type text extraction
│   ├── llm_agent.py     # OpenAI batch extraction with retry
│   ├── output_writer.py # Excel (color-coded) + CSV writers
│   ├── aras_push.py     # Aras OData REST push
│   └── worker.py        # Celery tasks (process_run, push_to_plm)
├── static/
│   └── app.html         # Complete SPA (single file, ~2600 lines)
├── data/
│   ├── plm_digitizer.db # SQLite database (auto-created)
│   └── outputs/         # Generated output files
├── requirements.txt
└── README.md
```

---

## Security

- **API keys and passwords** are encrypted at rest using Fernet symmetric encryption
- Encryption key is derived from a machine-specific seed (not stored anywhere)
- Sensitive values are never logged or exposed in API responses
- Settings masked in UI (show/hide toggle)

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve frontend SPA |
| GET | `/api/health` | Health check (Redis, DB) |
| POST | `/api/settings` | Save a setting |
| GET | `/api/settings` | Get all settings (masked) |
| POST | `/api/validate/openai` | Validate OpenAI key |
| POST | `/api/validate/folder` | Scan folder, return file breakdown |
| POST | `/api/validate/aras` | Test Aras connection |
| GET | `/api/runs` | List runs with filters |
| POST | `/api/runs` | Create & start a new run |
| GET | `/api/runs/{id}` | Get run details |
| DELETE | `/api/runs/{id}` | Cancel a running run |
| GET | `/api/runs/{id}/logs` | Paginated log entries |
| GET | `/api/runs/{id}/results` | Paginated file results |
| PATCH | `/api/runs/{id}/results/{rid}` | Edit extracted data |
| GET | `/api/runs/{id}/download` | Download output file |
| POST | `/api/runs/{id}/push` | Push to PLM |
| GET | `/api/runs/{id}/push/status` | Push progress |
| GET | `/api/dashboard/stats` | Aggregate stats + activity |
| POST | `/api/connections` | Create PLM connection |
| GET | `/api/connections` | List connections |
| POST | `/api/connections/{id}/test` | Test a connection |
| DELETE | `/api/connections/{id}` | Delete connection |
| WS | `/ws/runs/{id}` | Real-time run progress stream |

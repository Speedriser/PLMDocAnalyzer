"""
PLM Digitizer - Main FastAPI Application Entry Point
"""
import asyncio
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import APP_VERSION, STATIC_DIR
from database import init_db
from models import APIResponse

# Configure logging — console + rotating file
from logging.handlers import RotatingFileHandler
from pathlib import Path as _Path

_LOG_DIR = _Path(__file__).parent / "data"
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / "app.log"

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_file_handler = RotatingFileHandler(
    _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8", delay=True
)
_file_handler.setFormatter(_fmt)
_file_handler.setLevel(logging.DEBUG)   # capture DEBUG in file

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
_console_handler.setLevel(logging.INFO)

logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(_file_handler)
logging.root.addHandler(_console_handler)

# Silence overly noisy libs
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("openai._base_client").setLevel(logging.WARNING)
# pdfminer/pdfplumber emit DEBUG for every parsed PDF object — suppress them
# to avoid flooding the log file and triggering Windows file-lock errors on rotation
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info(f"Log file: {_LOG_FILE}")


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")

    # Start Celery worker only when Redis is available
    from config import USE_REDIS
    if USE_REDIS:
        logger.info("Redis detected — starting Celery worker...")
        _start_celery_worker()
        logger.info("Celery worker started")
    else:
        logger.info("Redis not available — using built-in thread pool for task execution")

    yield

    logger.info("Shutting down PLM Digitizer...")


def _start_celery_worker():
    """Start a Celery worker in a background thread (only called when Redis is available)."""
    def run_worker():
        try:
            from services.worker import celery_app
            if celery_app is None:
                logger.warning("Celery app not initialized — skipping worker start")
                return
            # Start worker with solo pool (no additional processes needed)
            celery_app.worker_main(
                argv=["worker", "--loglevel=info", "--pool=solo", "-c", "1"]
            )
        except Exception as e:
            logger.error(f"Celery worker error: {e}")

    thread = threading.Thread(target=run_worker, daemon=True, name="celery-worker")
    thread.start()


# ─── App Factory ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="PLM Digitizer",
    description="Document Intelligence Platform for PLM Systems",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global Error Handler ────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "error": "An internal error occurred"},
    )


# ─── Include Routers ─────────────────────────────────────────────────────────

from routers.settings import router as settings_router
from routers.runs import router as runs_router
from routers.files import router as files_router
from routers.push import router as push_router

app.include_router(settings_router)
app.include_router(runs_router)
app.include_router(files_router)
app.include_router(push_router)


# ─── WebSocket ───────────────────────────────────────────────────────────────

@app.websocket("/ws/runs/{run_id}")
async def websocket_run_progress(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time run progress streaming.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for run {run_id}")

    from services.worker import register_ws_callback, unregister_ws_callback
    from database import get_db_session, Run, RunLog

    # Event queue for thread-safe communication
    event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    def on_event(event: dict):
        try:
            event_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    register_ws_callback(run_id, on_event)

    try:
        # Send current run state immediately
        db = get_db_session()
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                await websocket.send_json({
                    "event": "state",
                    "run": {
                        "id": run.id,
                        "status": run.status,
                        "processed": run.processed_files,
                        "total": run.total_files,
                        "passed": run.passed_records,
                        "failed": run.failed_records,
                        "skipped": run.skipped_files,
                        "tokens_used": run.total_tokens_used,
                    },
                })
        finally:
            db.close()

        # Stream events
        while True:
            try:
                # Check for events with timeout (also allows ping/pong)
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=5.0)
                    await websocket.send_json(event)

                    # If completed or error, send a few more events then close
                    if event.get("event") in ("completed", "error"):
                        await asyncio.sleep(0.5)
                        break

                except asyncio.TimeoutError:
                    # Send heartbeat
                    await websocket.send_json({"event": "ping"})

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}")
    finally:
        unregister_ws_callback(run_id, on_event)
        logger.info(f"WebSocket disconnected for run {run_id}")


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=APIResponse)
async def health_check():
    """Health check endpoint."""
    health = {
        "status": "ok",
        "version": APP_VERSION,
        "redis": _check_redis(),
        "database": _check_database(),
    }
    return APIResponse(success=True, data=health)


def _check_redis() -> dict:
    from config import USE_REDIS, REDIS_URL
    if not USE_REDIS:
        return {"status": "not_configured", "note": "Using built-in thread pool"}
    try:
        import redis as redis_lib
        r = redis_lib.from_url(REDIS_URL, socket_timeout=2)
        r.ping()
        return {"status": "connected"}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}


def _check_database() -> dict:
    try:
        from database import get_db_session, Setting
        db = get_db_session()
        db.query(Setting).limit(1).all()
        db.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─── Serve Frontend ──────────────────────────────────────────────────────────

@app.get("/")
async def serve_frontend():
    """Serve the main SPA."""
    html_path = STATIC_DIR / "app.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return JSONResponse(
        content={"error": "Frontend not found. Ensure static/app.html exists."},
        status_code=404,
    )


# ─── Entrypoint ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )

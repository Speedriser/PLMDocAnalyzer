"""
PLM Digitizer - Background Task Runner
Works with Redis (Celery) when available, or falls back to a pure
ThreadPoolExecutor so the app runs without any external dependencies.
"""
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── In-process state (shared between FastAPI and worker threads) ─────────────

_cancel_flags: Dict[str, bool] = {}
_cancel_lock = threading.Lock()

_ws_connections: Dict[str, List] = {}   # run_id -> [callback, ...]
_ws_lock = threading.Lock()

# Thread pool used when Redis/Celery is unavailable
_thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="plm-worker")


# ─── WebSocket broadcast helpers ─────────────────────────────────────────────

def register_ws_callback(run_id: str, callback):
    with _ws_lock:
        _ws_connections.setdefault(run_id, []).append(callback)


def unregister_ws_callback(run_id: str, callback):
    with _ws_lock:
        lst = _ws_connections.get(run_id, [])
        try:
            lst.remove(callback)
        except ValueError:
            pass


def broadcast_event(run_id: str, event: dict):
    with _ws_lock:
        callbacks = list(_ws_connections.get(run_id, []))
    for cb in callbacks:
        try:
            cb(event)
        except Exception:
            pass


# ─── Cancellation helpers ─────────────────────────────────────────────────────

def request_cancel(run_id: str):
    with _cancel_lock:
        _cancel_flags[run_id] = True


def is_cancelled(run_id: str) -> bool:
    with _cancel_lock:
        return _cancel_flags.get(run_id, False)


def clear_cancel(run_id: str):
    with _cancel_lock:
        _cancel_flags.pop(run_id, None)


# ─── Error formatting helpers ─────────────────────────────────────────────────

def _friendly_llm_error(err_str: str, provider: str, model: str) -> str:
    """Convert a raw LLM API exception message into a concise, user-friendly string."""
    s = err_str.lower()
    if "401" in s or "authentication" in s or "invalid" in s and "key" in s:
        if provider == "azure":
            return (f"Azure API key is invalid or expired. "
                    f"Go to Settings → LLM and re-enter your Azure API Key.")
        return "OpenAI API key is invalid or expired. Go to Settings → LLM to update it."
    if "403" in s or "permission" in s or "quota" in s:
        return f"API quota exceeded or permission denied. Check your {provider.title()} account usage limits."
    if "404" in s or "not found" in s or "deployment" in s:
        if provider == "azure":
            return (f"Azure deployment '{model}' not found. "
                    f"Go to Settings → LLM → Deployment Name and enter the exact name from Azure AI Foundry.")
        return f"Model '{model}' not found. Check your model name in Settings."
    if "429" in s or "rate limit" in s or "too many" in s:
        return "Rate limit hit. The system will retry automatically — please wait."
    if "timeout" in s or "timed out" in s:
        return "API request timed out. Check your network connection and try again."
    if "connection" in s or "network" in s or "resolve" in s:
        if provider == "azure":
            return f"Cannot reach Azure endpoint. Check your Endpoint URL in Settings → LLM."
        return "Cannot connect to OpenAI. Check your network connection."
    if "context" in s and "length" in s:
        return "Document is too large for the model's context window. It will be split automatically."
    # Fall back to a truncated version of the raw error
    return err_str[:200] if len(err_str) > 200 else err_str


# ─── Core pipeline (called by both Celery task and direct thread) ─────────────

def _run_pipeline(run_id: str):
    """
    Full document-processing pipeline.
    Called directly in a daemon thread (no-Redis path) OR by a Celery worker.
    """
    from database import get_db_session, Run, RunLog, FileResult, Setting
    from services.file_discovery import discover_files_sync
    from services.extractor import extract_file
    from services.llm_agent import extract_batch
    from services.output_writer import create_writer, generate_output_path
    from config import decrypt_value, LLM_MODELS

    clear_cancel(run_id)
    db = get_db_session()

    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            logger.error(f"Run {run_id} not found")
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        db.commit()

        # ── helpers ──────────────────────────────────────────────────────────

        def log_it(level: str, message: str, file_path: Optional[str] = None):
            entry = RunLog(
                run_id=run_id, level=level, message=message,
                file_path=file_path, timestamp=datetime.utcnow(),
            )
            db.add(entry)
            db.commit()
            broadcast_event(run_id, {
                "event": "log", "level": level, "message": message,
                "timestamp": datetime.utcnow().isoformat(), "file_path": file_path,
            })

        # ── Stage 1: file discovery ───────────────────────────────────────────

        log_it("info", f"Starting run: {run.name}")
        log_it("info", f"Folder: {run.folder_path}")
        log_it("info", f"Model: {run.llm_model}  Workers: {run.worker_count}")
        log_it("info", "Stage 1: Discovering files…")

        files = []
        for meta in discover_files_sync(run.folder_path):
            if is_cancelled(run_id):
                log_it("warning", "Run cancelled during file discovery")
                run.status = "cancelled"
                db.commit()
                return
            files.append(meta)
            if len(files) % 1000 == 0:
                run.total_files = len(files)
                db.commit()
                log_it("info", f"Discovered {len(files)} files so far…")

        run.total_files = len(files)
        db.commit()
        log_it("info", f"Found {len(files)} files to process")

        if not files:
            log_it("warning", "No supported files found in folder")
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            db.commit()
            broadcast_event(run_id, {"event": "completed", "summary": _build_summary(run)})
            return

        # ── Set up output writer ──────────────────────────────────────────────

        if not run.output_file_path:
            run.output_file_path = generate_output_path(run.name, run.output_format)
            db.commit()

        writer = create_writer(
            run.output_file_path, run.output_format,
            run.output_fields, run.confidence_threshold,
        )

        # ── Load API key + provider settings ─────────────────────────────────

        def _get_setting(key: str) -> Optional[str]:
            row = db.query(Setting).filter(Setting.key == key).first()
            if not row:
                return None
            try:
                return decrypt_value(row.value) if row.is_encrypted else row.value
            except Exception:
                return row.value

        llm_provider = _get_setting("llm_provider") or "openai"
        azure_endpoint = _get_setting("azure_endpoint")
        azure_api_version = _get_setting("azure_api_version")
        azure_deployment = _get_setting("azure_deployment")
        ollama_base_url = _get_setting("ollama_base_url") or "http://localhost:11434"

        # API key resolution: Ollama needs no key; others do
        if llm_provider == "ollama":
            api_key = "ollama"   # dummy — Ollama ignores it
        elif llm_provider == "azure":
            api_key = _get_setting("azure_api_key") or _get_setting("openai_api_key")
        else:
            api_key = _get_setting("openai_api_key")

        if not api_key and llm_provider != "ollama":
            log_it("error", "API key not configured — go to Settings → LLM first")
            run.status = "failed"
            db.commit()
            return

        # Resolve effective model name
        effective_model = run.llm_model
        if llm_provider == "azure":
            effective_model = azure_deployment or run.llm_model
            log_it("info", f"Azure provider — deployment: {effective_model}")
        elif llm_provider == "ollama":
            log_it("info", f"Ollama provider — model: {effective_model} @ {ollama_base_url}")
        else:
            log_it("info", f"OpenAI provider — model: {effective_model}")

        # ── Stage 2 + 3: Extraction → LLM ────────────────────────────────────

        processed = passed = failed = skipped = total_tokens = 0
        start_time = time.time()
        extraction_batch: list = []

        def flush_llm_batch(batch: list):
            nonlocal passed, failed, total_tokens

            if not batch:
                return

            # Log what we are about to send to the LLM
            file_names = [os.path.basename(m.file_path) for m, _ in batch]
            log_it("info", f"Stage 3: LLM extracting {len(batch)} file(s): {', '.join(file_names)}")

            documents = [(i, (ex.raw_text if ex.success else ""))
                         for i, (_, ex) in enumerate(batch)]

            llm_error: Optional[str] = None
            try:
                results, tokens = extract_batch(
                    api_key=api_key, model=effective_model,
                    fields=run.output_fields, documents=documents,
                    provider=llm_provider,
                    azure_endpoint=azure_endpoint,
                    azure_api_version=azure_api_version,
                )
                total_tokens += tokens
            except Exception as e:
                # Surface the real API error clearly in the terminal
                llm_error = str(e)
                friendly = _friendly_llm_error(llm_error, llm_provider, effective_model)
                log_it("error", f"LLM API error: {friendly}")
                results = [None] * len(batch)

            for i, (meta, extraction) in enumerate(batch):
                result_data = results[i] if i < len(results) else None
                confidence = 0.0
                status = "failed"
                extracted: dict = {}
                source_hint = ""
                file_error: Optional[str] = None

                if not extraction.success:
                    # File extraction failed (e.g. corrupt PDF)
                    file_error = extraction.error_message or "File extraction failed"
                    log_it("warning", f"  ✗ {os.path.basename(meta.file_path)} — extraction error: {file_error}", meta.file_path)
                elif llm_error:
                    # LLM call failed for the whole batch
                    file_error = f"LLM error: {_friendly_llm_error(llm_error, llm_provider, effective_model)}"
                elif result_data and isinstance(result_data, dict):
                    confidence = float(result_data.pop("_confidence", 0.5))
                    source_hint = result_data.pop("_source_hint", "")
                    extracted = result_data
                    status = "passed" if confidence >= run.confidence_threshold else "failed"
                    if status == "passed":
                        preview = " · ".join(f"{k}: {v}" for k, v in list(extracted.items())[:3] if v)
                        log_it("success", f"  ✓ {os.path.basename(meta.file_path)} — confidence {confidence*100:.0f}% — {preview}", meta.file_path)
                    else:
                        file_error = f"Low confidence ({confidence*100:.0f}%) — threshold is {run.confidence_threshold*100:.0f}%"
                        log_it("warning", f"  ✗ {os.path.basename(meta.file_path)} — {file_error}", meta.file_path)
                else:
                    # LLM returned null for this document
                    file_error = "LLM returned no data for this document"
                    log_it("warning", f"  ✗ {os.path.basename(meta.file_path)} — {file_error}", meta.file_path)

                if status == "passed":
                    passed += 1
                else:
                    failed += 1

                processing_time = getattr(extraction, "processing_time_ms", 0) or 0
                writer.write_row(
                    file_path=meta.file_path, file_type=meta.file_type,
                    extracted_data=extracted, confidence=confidence,
                    status=status, processing_time_ms=processing_time,
                    extraction_method=extraction.extraction_method,
                )

                db.add(FileResult(
                    run_id=run_id, file_path=meta.file_path, file_type=meta.file_type,
                    status=status, extracted_data=extracted,
                    raw_text_snippet=(extraction.raw_text or "")[:500],
                    error_message=file_error or extraction.error_message,
                    confidence_score=confidence,
                    extraction_method=extraction.extraction_method,
                    processing_time_ms=processing_time,
                    char_count=extraction.char_count,
                    processed_at=datetime.utcnow(),
                ))

            db.commit()

        # Stage 2: Extract text from all files
        log_it("info", f"Stage 2: Extracting text from {run.total_files} file(s) "
                       f"using {run.worker_count} worker(s)…")

        # Extract files in a thread pool
        with ThreadPoolExecutor(max_workers=run.worker_count) as ex:
            future_map = {
                ex.submit(extract_file, m.file_path, m.file_type): m
                for m in files
            }

            for future in as_completed(future_map):
                if is_cancelled(run_id):
                    log_it("warning", "Run cancelled during processing")
                    run.status = "cancelled"
                    db.commit()
                    return

                meta = future_map[future]
                processed += 1

                try:
                    extraction = future.result()
                    extraction_batch.append((meta, extraction))
                except Exception as e:
                    skipped += 1
                    log_it("error", f"Extraction error: {meta.file_path}: {e}", meta.file_path)
                    continue

                # Log file extraction result immediately (before LLM batch)
                if extraction_batch and extraction_batch[-1][1].success:
                    ex_result = extraction_batch[-1][1]
                    char_info = f"{ex_result.char_count:,} chars" if ex_result.char_count else "no text"
                    log_it("info",
                           f"  📄 Extracted {os.path.basename(meta.file_path)} "
                           f"via {ex_result.extraction_method} ({char_info})",
                           meta.file_path)
                elif extraction_batch and not extraction_batch[-1][1].success:
                    ex_result = extraction_batch[-1][1]
                    log_it("warning",
                           f"  ⚠ Could not extract text from {os.path.basename(meta.file_path)}: "
                           f"{ex_result.error_message}",
                           meta.file_path)

                if len(extraction_batch) >= run.batch_size:
                    flush_llm_batch(extraction_batch)
                    extraction_batch = []

                # Broadcast progress — always on every file for small runs,
                # every 10 files for larger ones (keeps WS traffic reasonable)
                broadcast_interval = max(1, min(10, run.total_files // 10))
                if processed % broadcast_interval == 0 or processed == run.total_files:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = (run.total_files - processed) / rate if rate > 0 else 0
                    model_info = LLM_MODELS.get(run.llm_model, {})
                    cost = (total_tokens / 1000.0) * model_info.get("cost_per_1k_tokens", 0.0005)

                    run.processed_files = processed
                    run.passed_records = passed
                    run.failed_records = failed
                    run.skipped_files = skipped
                    run.total_tokens_used = total_tokens
                    db.commit()

                    broadcast_event(run_id, {
                        "event": "progress",
                        "processed": processed, "total": run.total_files,
                        "passed": passed, "failed": failed, "skipped": skipped,
                        "current_file": os.path.basename(meta.file_path),
                        "rate": f"{rate * 60:.0f} files/min" if rate > 0 else "calculating…",
                        "eta": _format_eta(remaining),
                        "tokens_used": total_tokens,
                        "estimated_cost": round(cost, 4),
                    })

                    if processed % 100 == 0:
                        log_it("info", f"Progress: {processed}/{run.total_files} files processed")

        # Flush leftover batch
        if extraction_batch:
            flush_llm_batch(extraction_batch)

        # ── Stage 4: finalise output file ────────────────────────────────────
        log_it("info", f"Stage 4: Writing output file ({run.output_format.upper()})…")
        writer.finalize({"id": run_id, "name": run.name,
                         "total_files": run.total_files, "llm_model": run.llm_model})
        log_it("info", f"  Output saved to: {os.path.basename(run.output_file_path)}")

        # ── Failure analysis (best-effort) ────────────────────────────────────
        if failed > 0:
            try:
                reasons = [r.error_message for r in
                           db.query(FileResult).filter(
                               FileResult.run_id == run_id,
                               FileResult.status == "failed",
                               FileResult.error_message.isnot(None)
                           ).limit(50).all()]
                if reasons:
                    from services.llm_agent import analyze_failures
                    run.failure_analysis = analyze_failures(
                        api_key=api_key, model=effective_model,
                        failure_reasons=reasons, total_failed=failed,
                        total_processed=processed,
                        provider=llm_provider,
                        azure_endpoint=azure_endpoint,
                        azure_api_version=azure_api_version,
                    )
            except Exception:
                pass

        # ── Final DB update ───────────────────────────────────────────────────
        model_info = LLM_MODELS.get(run.llm_model, {})
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.processed_files = processed
        run.passed_records = passed
        run.failed_records = failed
        run.skipped_files = skipped
        run.total_tokens_used = total_tokens
        run.estimated_cost = round(
            (total_tokens / 1000.0) * model_info.get("cost_per_1k_tokens", 0.0005), 4
        )
        db.commit()

        # Compose a meaningful completion message
        total_proc = passed + failed
        if total_proc == 0:
            completion_msg = f"Run completed — no files were processed"
        elif passed == 0:
            completion_msg = (
                f"Run completed — all {failed} file(s) failed. "
                f"Check the error messages above for details."
            )
        elif failed == 0:
            completion_msg = f"Run completed — all {passed} file(s) passed ✓"
        else:
            pct = round(passed / total_proc * 100)
            completion_msg = (
                f"Run completed — {passed} passed, {failed} failed ({pct}% pass rate)"
            )
        if skipped:
            completion_msg += f", {skipped} skipped"

        log_it("info" if passed > 0 else "warning",
               f"Stage 5: {completion_msg}")
        broadcast_event(run_id, {
            "event": "completed",
            "summary": _build_summary(run),
            "pass_count": passed,
            "fail_count": failed,
            "skipped_count": skipped,
        })

    except Exception as e:
        logger.exception(f"Run {run_id} crashed: {e}")
        try:
            run = db.query(Run).filter(Run.id == run_id).first()
            if run:
                run.status = "failed"
                run.error_summary = {"error": str(e)}
                run.completed_at = datetime.utcnow()
                db.commit()
            broadcast_event(run_id, {"event": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        db.close()
        clear_cancel(run_id)


def _push_pipeline(run_id: str, connection_id: str, field_mappings: dict, retry_failed: bool):
    """Push to PLM — runs in a background thread."""
    from database import get_db_session, Run, PLMConnection
    from services.aras_push import push_to_aras
    from config import decrypt_value

    db = get_db_session()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        conn = db.query(PLMConnection).filter(PLMConnection.id == connection_id).first()
        if not run or not conn:
            return

        run.push_status = "running"
        run.push_started_at = datetime.utcnow()
        db.commit()

        password = ""
        if conn.password_encrypted:
            try:
                password = decrypt_value(conn.password_encrypted)
            except Exception:
                password = conn.password_encrypted

        def progress_cb(pushed, total, failed_count):
            run.push_passed = pushed - failed_count
            run.push_failed = failed_count
            db.commit()
            broadcast_event(run_id, {
                "event": "push_progress",
                "pushed": pushed, "total": total, "failed": failed_count,
            })

        result = push_to_aras(
            output_file=run.output_file_path,
            connection_config={
                "server_url": conn.server_url,
                "database_name": conn.database_name,
                "username": conn.username,
                "password": password,
                "item_type": conn.item_type or "Part",
            },
            field_mapping=field_mappings,
            progress_callback=progress_cb,
        )

        run.push_status = "completed" if result.get("success") else "failed"
        run.push_passed = result.get("pushed", 0)
        run.push_failed = result.get("failed", 0)
        run.push_completed_at = datetime.utcnow()
        db.commit()
        broadcast_event(run_id, {"event": "push_completed", "summary": result})

    except Exception as e:
        logger.exception(f"Push task failed: {e}")
        run = db.query(Run).filter(Run.id == run_id).first()
        if run:
            run.push_status = "failed"
            db.commit()
    finally:
        db.close()


# ─── Public dispatch functions ────────────────────────────────────────────────
# These are called by the routers. They either queue a Celery task (Redis path)
# or submit directly to the thread pool (no-Redis path).

def process_run_task(run_id: str):
    """Start a processing run (Celery or direct thread)."""
    from config import USE_REDIS
    if USE_REDIS:
        try:
            _celery_process_run.delay(run_id)
            return
        except Exception as e:
            logger.warning(f"Celery unavailable ({e}), falling back to thread")
    _thread_pool.submit(_run_pipeline, run_id)


def push_to_plm_task(run_id: str, connection_id: str, field_mappings: dict, retry_failed: bool = False):
    """Start a PLM push (Celery or direct thread)."""
    from config import USE_REDIS
    if USE_REDIS:
        try:
            _celery_push_to_plm.delay(run_id, connection_id, field_mappings, retry_failed)
            return
        except Exception as e:
            logger.warning(f"Celery unavailable ({e}), falling back to thread")
    _thread_pool.submit(_push_pipeline, run_id, connection_id, field_mappings, retry_failed)


# ─── Celery tasks (only instantiated/used when Redis is available) ─────────────

def _make_celery_app():
    from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
    from celery import Celery
    app = Celery("plm_digitizer", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
    app.conf.update(
        task_serializer="json", accept_content=["json"],
        result_serializer="json", timezone="UTC", enable_utc=True,
        task_track_started=True, worker_prefetch_multiplier=1, task_acks_late=True,
    )
    return app


try:
    celery_app = _make_celery_app()

    @celery_app.task(bind=True, name="plm_digitizer.process_run")
    def _celery_process_run(self, run_id: str):
        _run_pipeline(run_id)

    @celery_app.task(bind=True, name="plm_digitizer.push_to_plm")
    def _celery_push_to_plm(self, run_id: str, connection_id: str,
                             field_mappings: dict, retry_failed: bool = False):
        _push_pipeline(run_id, connection_id, field_mappings, retry_failed)

except Exception as _celery_err:
    logger.warning(f"Celery init skipped ({_celery_err}) — using thread-based execution")
    celery_app = None
    _celery_process_run = None
    _celery_push_to_plm = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_summary(run) -> dict:
    return {
        "id": run.id, "name": run.name, "total_files": run.total_files,
        "processed": run.processed_files, "passed": run.passed_records,
        "failed": run.failed_records, "skipped": run.skipped_files,
        "output_file": run.output_file_path, "tokens_used": run.total_tokens_used,
        "estimated_cost": run.estimated_cost,
    }


def _format_eta(seconds: float) -> str:
    if seconds <= 0:
        return "calculating…"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"

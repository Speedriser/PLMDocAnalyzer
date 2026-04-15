"""
PLM Digitizer - Run Management Router
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db, Run, RunLog, FileResult, Setting, Preset, AuditLog
from models import (
    APIResponse, RunCreate, RunResponse, RunSummary,
    RunLogResponse, FileResultResponse, FileResultUpdate,
    PresetCreate, PresetResponse,
)
from config import decrypt_value

router = APIRouter(prefix="/api", tags=["runs"])
logger = logging.getLogger(__name__)


def _run_to_summary(run: Run) -> dict:
    duration = None
    if run.started_at and run.completed_at:
        duration = (run.completed_at - run.started_at).total_seconds()
    elif run.started_at:
        duration = (datetime.utcnow() - run.started_at).total_seconds()

    total = run.processed_files or 0
    passed = run.passed_records or 0
    pass_rate = round(passed / total * 100, 1) if total > 0 else 0

    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "folder_path": run.folder_path,
        "total_files": run.total_files,
        "processed_files": run.processed_files,
        "passed_records": run.passed_records,
        "failed_records": run.failed_records,
        "skipped_files": run.skipped_files,
        "pass_rate": pass_rate,
        "duration_seconds": duration,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "output_file_path": run.output_file_path,
        "push_status": run.push_status,
        "llm_model": run.llm_model,
        "output_format": run.output_format,
        "total_tokens_used": run.total_tokens_used,
        "estimated_cost": run.estimated_cost,
        "failure_analysis": run.failure_analysis,
        "error_summary": run.error_summary,
    }


@router.get("/runs", response_model=APIResponse)
async def list_runs(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    try:
        query = db.query(Run).order_by(Run.created_at.desc())

        if status:
            query = query.filter(Run.status == status)
        if search:
            query = query.filter(
                (Run.name.ilike(f"%{search}%")) |
                (Run.folder_path.ilike(f"%{search}%"))
            )

        total = query.count()
        runs = query.offset(offset).limit(limit).all()

        return APIResponse(
            success=True,
            data={
                "runs": [_run_to_summary(r) for r in runs],
                "total": total,
                "offset": offset,
                "limit": limit,
            },
        )
    except Exception as e:
        logger.exception(f"List runs failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list runs")


@router.post("/runs", response_model=APIResponse)
async def create_run(req: RunCreate, db: Session = Depends(get_db)):
    try:
        # Validate API key is configured — Ollama is local so no key needed
        llm_provider_setting = db.query(Setting).filter(Setting.key == "llm_provider").first()
        llm_provider = llm_provider_setting.value if llm_provider_setting else "openai"
        if llm_provider != "ollama":
            key_name = "azure_api_key" if llm_provider == "azure" else "openai_api_key"
            api_key_setting = (
                db.query(Setting).filter(Setting.key == key_name).first() or
                db.query(Setting).filter(Setting.key == "openai_api_key").first()
            )
            if not api_key_setting:
                return APIResponse(success=False, error="LLM API key not configured. Go to Settings > LLM first.")

        # Generate output path if not provided, or if the user gave a directory path
        from services.output_writer import generate_output_path
        import os as _os
        if req.output_file_path:
            _p = req.output_file_path.strip()
            # Treat the value as a base directory if it has no file extension OR is an
            # existing directory — auto-generate the filename inside that folder.
            _is_dir = _os.path.isdir(_p) or not _os.path.splitext(_p)[1]
            if _is_dir:
                output_path = generate_output_path(req.name, req.output_format, base_dir=_p)
            else:
                output_path = _p
        else:
            output_path = generate_output_path(req.name, req.output_format)

        run = Run(
            name=req.name,
            status="pending",
            folder_path=req.folder_path,
            output_fields=req.output_fields,
            output_format=req.output_format,
            output_file_path=output_path,
            target_system=req.target_system,
            llm_model=req.llm_model,
            worker_count=req.worker_count,
            batch_size=req.batch_size,
            confidence_threshold=req.confidence_threshold,
            plm_connection_id=req.plm_connection_id,
            auto_push=req.auto_push,
        )
        db.add(run)

        audit = AuditLog(
            action="run_created",
            entity_type="run",
            entity_id=run.id,
            details={"name": run.name, "folder": run.folder_path},
        )
        db.add(audit)
        db.commit()

        # Start processing (Celery or thread pool depending on Redis availability)
        from services.worker import process_run_task
        process_run_task(run.id)

        logger.info(f"Run {run.id} created and queued")
        return APIResponse(success=True, data=_run_to_summary(run))

    except Exception as e:
        logger.exception(f"Create run failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create run")


@router.get("/runs/{run_id}", response_model=APIResponse)
async def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return APIResponse(success=True, data=_run_to_summary(run))


@router.delete("/runs/{run_id}", response_model=APIResponse)
async def cancel_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ("running", "pending"):
        return APIResponse(success=False, error=f"Cannot cancel run in status: {run.status}")

    from services.worker import request_cancel
    request_cancel(run_id)

    run.status = "cancelled"
    run.completed_at = datetime.utcnow()
    db.commit()

    return APIResponse(success=True, data={"cancelled": True})


@router.get("/runs/{run_id}/logs", response_model=APIResponse)
async def get_run_logs(
    run_id: str,
    level: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(RunLog).filter(RunLog.run_id == run_id).order_by(RunLog.timestamp.desc())
    if level:
        query = query.filter(RunLog.level == level)
    total = query.count()
    logs = query.offset(offset).limit(limit).all()
    return APIResponse(
        success=True,
        data={
            "logs": [
                {
                    "id": l.id,
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                    "level": l.level,
                    "message": l.message,
                    "file_path": l.file_path,
                }
                for l in logs
            ],
            "total": total,
        },
    )


@router.get("/runs/{run_id}/results", response_model=APIResponse)
async def get_run_results(
    run_id: str,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(FileResult).filter(FileResult.run_id == run_id)
    if status:
        query = query.filter(FileResult.status == status)
    if search:
        query = query.filter(FileResult.file_path.ilike(f"%{search}%"))

    total = query.count()
    results = query.order_by(FileResult.id.desc()).offset(offset).limit(limit).all()

    return APIResponse(
        success=True,
        data={
            "results": [
                {
                    "id": r.id,
                    "file_path": r.file_path,
                    "file_type": r.file_type,
                    "status": r.status,
                    "confidence_score": r.confidence_score,
                    "extracted_data": r.extracted_data,
                    "raw_text_snippet": r.raw_text_snippet,
                    "error_message": r.error_message,
                    "extraction_method": r.extraction_method,
                    "processing_time_ms": r.processing_time_ms,
                    "char_count": r.char_count,
                    "manually_edited": r.manually_edited,
                    "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                }
                for r in results
            ],
            "total": total,
        },
    )


@router.patch("/runs/{run_id}/results/{result_id}", response_model=APIResponse)
async def update_file_result(
    run_id: str,
    result_id: int,
    req: FileResultUpdate,
    db: Session = Depends(get_db),
):
    result = db.query(FileResult).filter(
        FileResult.id == result_id,
        FileResult.run_id == run_id,
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    if req.extracted_data is not None:
        result.extracted_data = req.extracted_data
    if req.status is not None:
        result.status = req.status
    result.manually_edited = True
    db.commit()

    return APIResponse(success=True, data={"updated": True})


@router.get("/runs/{run_id}/download")
async def download_run_output(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.output_file_path:
        raise HTTPException(status_code=404, detail="Output file not available")
    if not Path(run.output_file_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found on disk")

    ext = Path(run.output_file_path).suffix
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext == ".xlsx"
        else "text/csv"
    )
    filename = Path(run.output_file_path).name

    return FileResponse(
        run.output_file_path,
        media_type=media_type,
        filename=filename,
    )


@router.post("/runs/{run_id}/reprocess", response_model=APIResponse)
async def reprocess_run(run_id: str, db: Session = Depends(get_db)):
    """Re-run with same configuration."""
    original = db.query(Run).filter(Run.id == run_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Run not found")

    from services.output_writer import generate_output_path
    new_name = f"{original.name} (Retry)"
    new_output = generate_output_path(new_name, original.output_format)

    new_run = Run(
        name=new_name,
        status="pending",
        folder_path=original.folder_path,
        output_fields=original.output_fields,
        output_format=original.output_format,
        output_file_path=new_output,
        target_system=original.target_system,
        llm_model=original.llm_model,
        worker_count=original.worker_count,
        batch_size=original.batch_size,
        confidence_threshold=original.confidence_threshold,
        plm_connection_id=original.plm_connection_id,
        auto_push=original.auto_push,
    )
    db.add(new_run)
    db.commit()

    from services.worker import process_run_task
    process_run_task(new_run.id)

    return APIResponse(success=True, data=_run_to_summary(new_run))


@router.get("/dashboard/stats", response_model=APIResponse)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    try:
        # Aggregate stats
        total_runs = db.query(Run).count()
        total_processed = db.query(func.sum(Run.processed_files)).scalar() or 0
        total_passed = db.query(func.sum(Run.passed_records)).scalar() or 0
        active_runs = db.query(Run).filter(Run.status == "running").count()
        failed_runs = db.query(Run).filter(Run.status == "failed").count()

        pass_rate = round(total_passed / total_processed * 100, 1) if total_processed > 0 else 0

        # Daily activity — last 30 days
        from datetime import date, timedelta as td
        daily_activity = []
        for i in range(29, -1, -1):
            day = datetime.utcnow().date() - td(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())

            day_runs = db.query(Run).filter(
                Run.created_at >= day_start,
                Run.created_at <= day_end,
            ).all()

            day_processed = sum(r.processed_files or 0 for r in day_runs)
            day_passed = sum(r.passed_records or 0 for r in day_runs)
            day_failed = sum(r.failed_records or 0 for r in day_runs)

            daily_activity.append({
                "date": day.isoformat(),
                "processed": day_processed,
                "passed": day_passed,
                "failed": day_failed,
                "runs": len(day_runs),
            })

        # Recent runs
        recent = db.query(Run).order_by(Run.created_at.desc()).limit(10).all()

        return APIResponse(
            success=True,
            data={
                "total_runs": total_runs,
                "total_files_processed": total_processed,
                "overall_pass_rate": pass_rate,
                "total_records_extracted": total_passed,
                "active_runs": active_runs,
                "failed_runs": failed_runs,
                "daily_activity": daily_activity,
                "recent_runs": [_run_to_summary(r) for r in recent],
            },
        )
    except Exception as e:
        logger.exception(f"Dashboard stats failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stats")


# ─── Presets ─────────────────────────────────────────────────────────────────

@router.post("/presets", response_model=APIResponse)
async def create_preset(req: PresetCreate, db: Session = Depends(get_db)):
    try:
        existing = db.query(Preset).filter(Preset.name == req.name).first()
        if existing:
            existing.config = req.config
            existing.updated_at = datetime.utcnow()
        else:
            preset = Preset(name=req.name, config=req.config)
            db.add(preset)
        db.commit()
        return APIResponse(success=True, data={"saved": True, "name": req.name})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to save preset")


@router.get("/presets", response_model=APIResponse)
async def list_presets(db: Session = Depends(get_db)):
    presets = db.query(Preset).order_by(Preset.created_at.desc()).all()
    return APIResponse(
        success=True,
        data=[
            {
                "id": p.id,
                "name": p.name,
                "config": p.config,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in presets
        ],
    )


@router.delete("/presets/{preset_id}", response_model=APIResponse)
async def delete_preset(preset_id: str, db: Session = Depends(get_db)):
    preset = db.query(Preset).filter(Preset.id == preset_id).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    db.delete(preset)
    db.commit()
    return APIResponse(success=True, data={"deleted": True})


# ─── Field Suggestions ────────────────────────────────────────────────────────

@router.post("/suggest/fields", response_model=APIResponse)
async def suggest_fields(req: dict, db: Session = Depends(get_db)):
    try:
        api_key_setting = db.query(Setting).filter(Setting.key == "openai_api_key").first()
        if not api_key_setting:
            return APIResponse(success=False, error="OpenAI API key not configured")

        api_key = decrypt_value(api_key_setting.value) if api_key_setting.is_encrypted else api_key_setting.value

        # Get model preference
        model_setting = db.query(Setting).filter(Setting.key == "default_model").first()
        model = model_setting.value if model_setting else "gpt-4o-mini"

        from services.llm_agent import suggest_fields as llm_suggest
        suggestions = llm_suggest(
            api_key=api_key,
            model=model,
            current_fields=req.get("current_fields", []),
            file_types=req.get("file_types"),
            context=req.get("context"),
        )
        return APIResponse(success=True, data=suggestions)
    except Exception as e:
        logger.exception(f"Field suggestion failed: {e}")
        return APIResponse(success=False, error=str(e))


# ─── Audit Log ────────────────────────────────────────────────────────────────

@router.get("/audit", response_model=APIResponse)
async def get_audit_log(
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    total = db.query(AuditLog).count()
    entries = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()
    return APIResponse(
        success=True,
        data={
            "entries": [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "action": e.action,
                    "entity_type": e.entity_type,
                    "entity_id": e.entity_id,
                    "details": e.details,
                }
                for e in entries
            ],
            "total": total,
        },
    )

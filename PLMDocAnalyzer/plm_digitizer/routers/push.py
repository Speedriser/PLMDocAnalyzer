"""
PLM Digitizer - PLM Push Router (Connections + Push management)
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, PLMConnection, Run, Setting, AuditLog
from models import APIResponse, PLMConnectionCreate, PushRequest
from config import encrypt_value, decrypt_value

router = APIRouter(prefix="/api", tags=["plm"])
logger = logging.getLogger(__name__)


# ─── PLM Connections ─────────────────────────────────────────────────────────

@router.post("/connections", response_model=APIResponse)
async def create_connection(req: PLMConnectionCreate, db: Session = Depends(get_db)):
    try:
        encrypted_pw = None
        if req.password:
            encrypted_pw = encrypt_value(req.password)

        conn = PLMConnection(
            name=req.name,
            system_type=req.system_type,
            server_url=req.server_url,
            database_name=req.database_name,
            username=req.username,
            password_encrypted=encrypted_pw,
            item_type=req.item_type,
            test_status="untested",
        )
        db.add(conn)

        audit = AuditLog(
            action="connection_created",
            entity_type="plm_connection",
            entity_id=conn.id,
            details={"name": req.name, "system_type": req.system_type},
        )
        db.add(audit)
        db.commit()

        return APIResponse(success=True, data=_conn_to_dict(conn))
    except Exception as e:
        logger.exception(f"Create connection failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create connection")


@router.get("/connections", response_model=APIResponse)
async def list_connections(db: Session = Depends(get_db)):
    connections = db.query(PLMConnection).order_by(PLMConnection.created_at.desc()).all()
    return APIResponse(
        success=True,
        data=[_conn_to_dict(c) for c in connections],
    )


@router.delete("/connections/{connection_id}", response_model=APIResponse)
async def delete_connection(connection_id: str, db: Session = Depends(get_db)):
    conn = db.query(PLMConnection).filter(PLMConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(conn)
    db.commit()
    return APIResponse(success=True, data={"deleted": True})


@router.post("/connections/{connection_id}/test", response_model=APIResponse)
async def test_connection(connection_id: str, db: Session = Depends(get_db)):
    conn = db.query(PLMConnection).filter(PLMConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        from services.aras_push import test_aras_connection

        password = ""
        if conn.password_encrypted:
            try:
                password = decrypt_value(conn.password_encrypted)
            except Exception:
                password = conn.password_encrypted

        success, message = test_aras_connection(
            conn.server_url, conn.database_name, conn.username, password
        )

        conn.last_tested_at = datetime.utcnow()
        conn.test_status = "success" if success else "failed"
        conn.test_message = message
        db.commit()

        return APIResponse(
            success=success,
            data={"message": message, "status": conn.test_status},
            error=None if success else message,
        )
    except Exception as e:
        conn.last_tested_at = datetime.utcnow()
        conn.test_status = "failed"
        conn.test_message = str(e)
        db.commit()
        return APIResponse(success=False, error=str(e))


@router.put("/connections/{connection_id}", response_model=APIResponse)
async def update_connection(
    connection_id: str,
    req: PLMConnectionCreate,
    db: Session = Depends(get_db),
):
    conn = db.query(PLMConnection).filter(PLMConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    conn.name = req.name
    conn.system_type = req.system_type
    conn.server_url = req.server_url
    conn.database_name = req.database_name
    conn.username = req.username
    conn.item_type = req.item_type
    if req.password:
        conn.password_encrypted = encrypt_value(req.password)
    conn.test_status = "untested"

    db.commit()
    return APIResponse(success=True, data=_conn_to_dict(conn))


# ─── Push Operations ─────────────────────────────────────────────────────────

@router.post("/runs/{run_id}/push", response_model=APIResponse)
async def push_to_plm(run_id: str, req: PushRequest, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if not run.output_file_path:
        return APIResponse(success=False, error="Run has no output file")

    conn = db.query(PLMConnection).filter(PLMConnection.id == req.connection_id).first()
    if not conn:
        return APIResponse(success=False, error="Connection not found")

    # If no field mappings provided, try to auto-generate
    field_mappings = req.field_mappings
    if not field_mappings:
        field_mappings = {f: f.lower().replace(" ", "_") for f in run.output_fields}

    # Start async push task
    from services.worker import push_to_plm_task
    push_to_plm_task(run_id, req.connection_id, field_mappings, req.retry_failed)

    run.push_status = "pending"
    db.commit()

    return APIResponse(
        success=True,
        data={"message": "Push started", "run_id": run_id},
    )


@router.get("/runs/{run_id}/push/status", response_model=APIResponse)
async def get_push_status(run_id: str, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    total = run.processed_files or 0
    return APIResponse(
        success=True,
        data={
            "status": run.push_status,
            "total_records": total,
            "pushed": run.push_passed,
            "failed": run.push_failed,
            "started_at": run.push_started_at.isoformat() if run.push_started_at else None,
            "completed_at": run.push_completed_at.isoformat() if run.push_completed_at else None,
        },
    )


@router.post("/runs/{run_id}/suggest-mappings", response_model=APIResponse)
async def suggest_field_mappings(run_id: str, req: dict, db: Session = Depends(get_db)):
    """Use AI to suggest field mappings between output columns and Aras properties."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    api_key_setting = db.query(Setting).filter(Setting.key == "openai_api_key").first()
    if not api_key_setting:
        return APIResponse(success=False, error="OpenAI API key not configured")

    try:
        api_key = decrypt_value(api_key_setting.value) if api_key_setting.is_encrypted else api_key_setting.value
        model_setting = db.query(Setting).filter(Setting.key == "default_model").first()
        model = model_setting.value if model_setting else "gpt-4o-mini"

        from services.llm_agent import suggest_field_mappings as llm_mappings
        aras_props = req.get("aras_properties")
        mappings = llm_mappings(api_key, model, run.output_fields, aras_props)
        return APIResponse(success=True, data=mappings)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


def _conn_to_dict(conn: PLMConnection) -> dict:
    return {
        "id": conn.id,
        "name": conn.name,
        "system_type": conn.system_type,
        "server_url": conn.server_url,
        "database_name": conn.database_name,
        "username": conn.username,
        "item_type": conn.item_type,
        "created_at": conn.created_at.isoformat() if conn.created_at else None,
        "last_tested_at": conn.last_tested_at.isoformat() if conn.last_tested_at else None,
        "test_status": conn.test_status,
        "test_message": conn.test_message,
    }

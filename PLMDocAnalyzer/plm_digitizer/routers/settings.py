"""
PLM Digitizer - Settings Router
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Setting, AuditLog
from models import APIResponse, SettingCreate, SettingResponse
from config import encrypt_value, decrypt_value

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)

# Keys that should always be encrypted
ENCRYPTED_KEYS = {"openai_api_key", "password", "secret"}


def _mask_value(key: str, value: str) -> str:
    """Mask sensitive values for API responses."""
    if any(k in key.lower() for k in ["key", "password", "secret", "token"]):
        if len(value) > 8:
            return value[:4] + "*" * (len(value) - 8) + value[-4:]
        return "****"
    return value


@router.post("", response_model=APIResponse)
async def save_setting(req: SettingCreate, db: Session = Depends(get_db)):
    try:
        should_encrypt = req.is_encrypted or any(
            k in req.key.lower() for k in ["key", "password", "secret", "token"]
        )

        stored_value = encrypt_value(req.value) if should_encrypt else req.value

        existing = db.query(Setting).filter(Setting.key == req.key).first()
        if existing:
            existing.value = stored_value
            existing.is_encrypted = should_encrypt
            existing.updated_at = datetime.utcnow()
        else:
            setting = Setting(
                key=req.key,
                value=stored_value,
                is_encrypted=should_encrypt,
                updated_at=datetime.utcnow(),
            )
            db.add(setting)

        # Audit log
        audit = AuditLog(
            action="setting_updated",
            entity_type="setting",
            entity_id=req.key,
            details={"key": req.key},
        )
        db.add(audit)
        db.commit()

        return APIResponse(success=True, data={"key": req.key, "saved": True})
    except Exception as e:
        logger.exception(f"Failed to save setting: {e}")
        raise HTTPException(status_code=500, detail="Failed to save setting")


@router.get("", response_model=APIResponse)
async def get_all_settings(db: Session = Depends(get_db)):
    try:
        settings = db.query(Setting).all()
        result = {}
        for s in settings:
            if s.is_encrypted:
                # Return masked value
                try:
                    decrypted = decrypt_value(s.value)
                    result[s.key] = _mask_value(s.key, decrypted)
                except Exception:
                    result[s.key] = "****"
            else:
                result[s.key] = s.value
        return APIResponse(success=True, data=result)
    except Exception as e:
        logger.exception(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get settings")


@router.delete("/{key}", response_model=APIResponse)
async def delete_setting(key: str, db: Session = Depends(get_db)):
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if not setting:
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
        db.delete(setting)
        audit = AuditLog(
            action="setting_deleted",
            entity_type="setting",
            entity_id=key,
            details={"key": key},
        )
        db.add(audit)
        db.commit()
        return APIResponse(success=True, data={"key": key, "deleted": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete setting: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete setting")


@router.post("/export", response_model=APIResponse)
async def export_settings(db: Session = Depends(get_db)):
    """Export all non-sensitive settings as JSON."""
    try:
        settings = db.query(Setting).all()
        export_data = {}
        for s in settings:
            if not s.is_encrypted:
                export_data[s.key] = s.value
        return APIResponse(success=True, data=export_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Export failed")

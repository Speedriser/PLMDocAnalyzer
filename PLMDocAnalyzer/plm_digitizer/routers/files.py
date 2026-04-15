"""
PLM Digitizer - File Discovery and Validation Router
"""
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models import APIResponse, FolderValidationRequest, FolderValidationResponse
from services.file_discovery import count_files, estimate_processing_time

router = APIRouter(prefix="/api/validate", tags=["validation"])
logger = logging.getLogger(__name__)


@router.post("/folder", response_model=APIResponse)
async def validate_folder(req: FolderValidationRequest):
    """
    Validate a folder path and return file type breakdown.
    """
    try:
        folder = Path(req.folder_path)

        if not folder.exists():
            return APIResponse(
                success=False,
                error=f"Folder does not exist: {req.folder_path}",
                data=FolderValidationResponse(
                    valid=False,
                    total_files=0,
                    file_breakdown={},
                    estimated_processing_time_minutes=0,
                    estimated_cost_usd=0,
                    error="Folder does not exist",
                ).model_dump(),
            )

        if not folder.is_dir():
            return APIResponse(
                success=False,
                error="Path is not a directory",
                data=FolderValidationResponse(
                    valid=False,
                    total_files=0,
                    file_breakdown={},
                    estimated_processing_time_minutes=0,
                    estimated_cost_usd=0,
                    error="Not a directory",
                ).model_dump(),
            )

        total, breakdown = await count_files(req.folder_path)
        est_minutes, est_cost = estimate_processing_time(breakdown)

        response = FolderValidationResponse(
            valid=True,
            total_files=total,
            file_breakdown=breakdown,
            estimated_processing_time_minutes=round(est_minutes, 1),
            estimated_cost_usd=round(est_cost, 4),
        )

        return APIResponse(success=True, data=response.model_dump())

    except Exception as e:
        logger.exception(f"Folder validation failed: {e}")
        raise HTTPException(status_code=500, detail="Validation failed")


@router.post("/openai", response_model=APIResponse)
async def validate_openai(req: dict):
    """
    Validate OpenAI API key (direct OpenAI endpoint).
    """
    api_key = req.get("api_key", "")
    model = req.get("model", "gpt-4o-mini")

    if not api_key:
        return APIResponse(success=False, error="API key is required")

    try:
        from services.llm_agent import validate_api_key
        is_valid, message, models = validate_api_key(api_key, model, provider="openai")

        return APIResponse(
            success=is_valid,
            data={"message": message, "available_models": models[:20]},
            error=None if is_valid else message,
        )
    except Exception as e:
        logger.exception(f"OpenAI validation failed: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/azure-openai", response_model=APIResponse)
async def validate_azure_openai(req: dict):
    """
    Validate Azure OpenAI credentials.

    Expects:
      api_key        - Azure resource key (from Azure Portal > Keys and Endpoint)
      azure_endpoint - Full endpoint URL, e.g. https://<resource>.openai.azure.com/
      deployment     - Deployment name configured in Azure AI Foundry
      api_version    - Optional; defaults to 2024-08-01-preview
    """
    api_key = req.get("api_key", "").strip()
    azure_endpoint = req.get("azure_endpoint", "").strip()
    deployment = req.get("deployment", "").strip()
    api_version = req.get("api_version", "").strip() or None

    if not api_key:
        return APIResponse(success=False, error="API key is required")
    if not azure_endpoint:
        return APIResponse(success=False, error="Azure endpoint URL is required")
    if not deployment:
        return APIResponse(success=False, error="Deployment name is required")

    try:
        from services.llm_agent import validate_api_key, _normalise_azure_endpoint
        normalised = _normalise_azure_endpoint(azure_endpoint)
        logger.info(f"Azure validation — endpoint: {azure_endpoint!r} → {normalised!r}, deployment: {deployment!r}")
        is_valid, message, deployments = validate_api_key(
            api_key=api_key,
            model=deployment,
            provider="azure",
            azure_endpoint=azure_endpoint,
            azure_api_version=api_version,
            azure_deployment=deployment,
        )
        return APIResponse(
            success=is_valid,
            data={
                "message": message,
                "deployment": deployment,
                "normalised_endpoint": normalised,
            },
            error=None if is_valid else message,
        )
    except Exception as e:
        logger.exception(f"Azure OpenAI validation failed: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/ollama", response_model=APIResponse)
async def validate_ollama(req: dict):
    """
    Validate that Ollama is running and a specific model is installed.

    Expects:
      base_url  - Ollama server URL (default: http://localhost:11434)
      model     - Model name to check, e.g. "qwen2.5:7b"
    """
    base_url = req.get("base_url", "http://localhost:11434").strip() or "http://localhost:11434"
    model = req.get("model", "").strip()

    try:
        from services.llm_agent import validate_api_key
        is_valid, message, models = validate_api_key(
            api_key="ollama",   # Ollama requires no key — pass dummy
            model=model,
            provider="ollama",
            ollama_base_url=base_url,
        )
        return APIResponse(
            success=is_valid,
            data={"message": message, "installed_models": models},
            error=None if is_valid else message,
        )
    except Exception as e:
        logger.exception(f"Ollama validation failed: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/aras", response_model=APIResponse)
async def validate_aras(req: dict):
    """
    Test Aras connection.
    """
    server_url = req.get("server_url", "")
    database_name = req.get("database_name")
    username = req.get("username")
    password = req.get("password")

    if not server_url:
        return APIResponse(success=False, error="Server URL is required")

    try:
        from services.aras_push import test_aras_connection
        success, message = test_aras_connection(server_url, database_name, username, password)
        return APIResponse(
            success=success,
            data={"message": message},
            error=None if success else message,
        )
    except Exception as e:
        logger.exception(f"Aras validation failed: {e}")
        return APIResponse(success=False, error=str(e))

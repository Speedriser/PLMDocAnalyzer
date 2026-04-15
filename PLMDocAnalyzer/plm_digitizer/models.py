"""
PLM Digitizer - Pydantic Schemas
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# ─── Standard API Response ───────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None


# ─── Settings ────────────────────────────────────────────────────────────────

class SettingCreate(BaseModel):
    key: str
    value: str
    is_encrypted: bool = False


class SettingResponse(BaseModel):
    id: int
    key: str
    value: Optional[str]
    is_encrypted: bool
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Run ─────────────────────────────────────────────────────────────────────

class RunCreate(BaseModel):
    name: str
    folder_path: str
    output_fields: List[str]
    output_format: str = "excel"
    output_file_path: Optional[str] = None
    target_system: Optional[str] = None
    llm_model: str = "gpt-4o-mini"
    worker_count: int = Field(default=4, ge=1, le=16)
    batch_size: int = Field(default=10, ge=1, le=50)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    plm_connection_id: Optional[str] = None
    auto_push: bool = False


class RunUpdate(BaseModel):
    status: Optional[str] = None
    processed_files: Optional[int] = None
    passed_records: Optional[int] = None
    failed_records: Optional[int] = None
    skipped_files: Optional[int] = None
    total_files: Optional[int] = None
    error_summary: Optional[Dict] = None
    output_file_path: Optional[str] = None


class RunResponse(BaseModel):
    id: str
    name: str
    status: str
    folder_path: str
    output_fields: List[str]
    output_format: str
    output_file_path: Optional[str]
    target_system: Optional[str]
    llm_model: str
    worker_count: int
    batch_size: int
    confidence_threshold: float
    plm_connection_id: Optional[str]
    auto_push: bool
    total_files: int
    processed_files: int
    passed_records: int
    failed_records: int
    skipped_files: int
    push_status: Optional[str]
    push_passed: int
    push_failed: int
    total_tokens_used: int
    estimated_cost: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    error_summary: Optional[Dict]
    failure_analysis: Optional[str]

    class Config:
        from_attributes = True


class RunSummary(BaseModel):
    id: str
    name: str
    status: str
    folder_path: str
    total_files: int
    processed_files: int
    passed_records: int
    failed_records: int
    skipped_files: int
    pass_rate: float = 0.0
    duration_seconds: Optional[float] = None
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    output_file_path: Optional[str]
    push_status: Optional[str]

    class Config:
        from_attributes = True


# ─── Run Logs ─────────────────────────────────────────────────────────────────

class RunLogResponse(BaseModel):
    id: int
    run_id: str
    timestamp: datetime
    level: str
    message: str
    file_path: Optional[str]

    class Config:
        from_attributes = True


# ─── File Results ─────────────────────────────────────────────────────────────

class FileResultResponse(BaseModel):
    id: int
    run_id: str
    file_path: str
    file_type: Optional[str]
    status: str
    extracted_data: Optional[Dict]
    raw_text_snippet: Optional[str]
    error_message: Optional[str]
    confidence_score: Optional[float]
    extraction_method: Optional[str]
    processing_time_ms: Optional[int]
    char_count: int
    processed_at: Optional[datetime]
    manually_edited: bool

    class Config:
        from_attributes = True


class FileResultUpdate(BaseModel):
    extracted_data: Optional[Dict] = None
    status: Optional[str] = None
    manually_edited: bool = True


# ─── PLM Connections ─────────────────────────────────────────────────────────

class PLMConnectionCreate(BaseModel):
    name: str
    system_type: str = "aras"
    server_url: str
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    item_type: Optional[str] = None


class PLMConnectionResponse(BaseModel):
    id: str
    name: str
    system_type: str
    server_url: str
    database_name: Optional[str]
    username: Optional[str]
    item_type: Optional[str]
    created_at: datetime
    last_tested_at: Optional[datetime]
    test_status: Optional[str]
    test_message: Optional[str]

    class Config:
        from_attributes = True


# ─── Presets ─────────────────────────────────────────────────────────────────

class PresetCreate(BaseModel):
    name: str
    config: Dict


class PresetResponse(BaseModel):
    id: str
    name: str
    config: Dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Validation ──────────────────────────────────────────────────────────────

class OpenAIValidationRequest(BaseModel):
    api_key: str
    model: Optional[str] = "gpt-4o-mini"


class FolderValidationRequest(BaseModel):
    folder_path: str


class FolderValidationResponse(BaseModel):
    valid: bool
    total_files: int
    file_breakdown: Dict[str, int]
    estimated_processing_time_minutes: float
    estimated_cost_usd: float
    error: Optional[str] = None


class ArasValidationRequest(BaseModel):
    server_url: str
    database_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


# ─── Dashboard ───────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_runs: int
    total_files_processed: int
    overall_pass_rate: float
    total_records_extracted: int
    active_runs: int
    failed_runs: int
    daily_activity: List[Dict]
    recent_runs: List[RunSummary]


# ─── WebSocket Events ────────────────────────────────────────────────────────

class ProgressEvent(BaseModel):
    event: str = "progress"
    processed: int
    total: int
    passed: int
    failed: int
    skipped: int
    current_file: Optional[str]
    rate: str
    eta: str
    tokens_used: int
    estimated_cost: float


class LogEvent(BaseModel):
    event: str = "log"
    level: str
    message: str
    timestamp: str
    file_path: Optional[str] = None


class CompletedEvent(BaseModel):
    event: str = "completed"
    summary: Dict


class ErrorEvent(BaseModel):
    event: str = "error"
    message: str


# ─── Push ────────────────────────────────────────────────────────────────────

class PushRequest(BaseModel):
    connection_id: str
    item_type: str
    field_mappings: Optional[Dict[str, str]] = None
    retry_failed: bool = False


class PushStatusResponse(BaseModel):
    status: str
    total_records: int
    pushed: int
    failed: int
    message: Optional[str]


# ─── Field Suggestions ───────────────────────────────────────────────────────

class FieldSuggestionRequest(BaseModel):
    current_fields: List[str]
    file_types: Optional[List[str]] = None
    context: Optional[str] = None


class FieldMappingSuggestion(BaseModel):
    output_column: str
    aras_property: str
    confidence: float
    reason: str


# ─── Notifications ───────────────────────────────────────────────────────────

class Notification(BaseModel):
    id: str
    type: str  # success/error/warning/info
    title: str
    message: str
    timestamp: datetime
    read: bool = False
    run_id: Optional[str] = None

"""
PLM Digitizer - SQLAlchemy Models and Database Initialization
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine, Column, String, Boolean, DateTime,
    Integer, Float, Text, ForeignKey, JSON, event
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, Session
from sqlalchemy.pool import StaticPool

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Run(Base):
    __tablename__ = "runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")  # pending/running/completed/failed/cancelled
    folder_path = Column(Text, nullable=False)
    output_fields = Column(JSON, default=list)
    output_format = Column(String(10), default="excel")  # excel/csv
    output_file_path = Column(Text, nullable=True)
    target_system = Column(String(100), nullable=True)
    llm_model = Column(String(100), default="gpt-4o-mini")
    worker_count = Column(Integer, default=4)
    batch_size = Column(Integer, default=10)
    confidence_threshold = Column(Float, default=0.7)
    plm_connection_id = Column(String(36), ForeignKey("plm_connections.id"), nullable=True)
    auto_push = Column(Boolean, default=False)

    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    passed_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)
    skipped_files = Column(Integer, default=0)

    push_status = Column(String(50), nullable=True)
    push_passed = Column(Integer, default=0)
    push_failed = Column(Integer, default=0)
    push_started_at = Column(DateTime, nullable=True)
    push_completed_at = Column(DateTime, nullable=True)

    total_tokens_used = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    error_summary = Column(JSON, default=dict)
    failure_analysis = Column(Text, nullable=True)

    logs = relationship("RunLog", back_populates="run", cascade="all, delete-orphan")
    file_results = relationship("FileResult", back_populates="run", cascade="all, delete-orphan")
    plm_connection = relationship("PLMConnection", back_populates="runs")


class RunLog(Base):
    __tablename__ = "run_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("runs.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(20), default="info")  # info/warning/error
    message = Column(Text, nullable=False)
    file_path = Column(Text, nullable=True)

    run = relationship("Run", back_populates="logs")


class FileResult(Base):
    __tablename__ = "file_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("runs.id"), nullable=False, index=True)
    file_path = Column(Text, nullable=False)
    file_type = Column(String(20), nullable=True)
    status = Column(String(20), default="pending")  # passed/failed/skipped
    extracted_data = Column(JSON, default=dict)
    raw_text_snippet = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    extraction_method = Column(String(50), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    char_count = Column(Integer, default=0)
    processed_at = Column(DateTime, nullable=True)
    manually_edited = Column(Boolean, default=False)

    run = relationship("Run", back_populates="file_results")


class PLMConnection(Base):
    __tablename__ = "plm_connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    system_type = Column(String(50), default="aras")
    server_url = Column(Text, nullable=False)
    database_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    password_encrypted = Column(Text, nullable=True)
    item_type = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_tested_at = Column(DateTime, nullable=True)
    test_status = Column(String(50), nullable=True)  # success/failed/untested
    test_message = Column(Text, nullable=True)

    runs = relationship("Run", back_populates="plm_connection")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    action = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(String(255), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)


class Preset(Base):
    __tablename__ = "presets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True)
    config = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Engine and session setup
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    poolclass=StaticPool if "sqlite" in DATABASE_URL else None,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a direct session (for use outside FastAPI)."""
    return SessionLocal()

"""
PLM Digitizer - Application Configuration
"""
import os
import uuid
import platform
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
import base64


BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/plm_digitizer.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

APP_VERSION = "1.0.0"
APP_BUILD_DATE = "2024-01-01"

# Celery broker � falls back to in-memory if Redis is not running
def _redis_available() -> bool:
    try:
        import redis as _redis
        r = _redis.from_url(REDIS_URL, socket_connect_timeout=1)
        r.ping()
        return True
    except Exception:
        return False

USE_REDIS = _redis_available()

CELERY_BROKER_URL = REDIS_URL if USE_REDIS else "memory://"
CELERY_RESULT_BACKEND = REDIS_URL if USE_REDIS else "cache+memory://"

# Processing defaults
DEFAULT_WORKER_COUNT = 4
DEFAULT_BATCH_SIZE = 10
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
MAX_FILE_SIZE_MB = 100

# OCR
OCR_LANGUAGE = "eng"

# Encryption
def _get_machine_key() -> bytes:
    """Derive a machine-specific encryption key."""
    machine_id = (
        platform.node() +
        platform.machine() +
        str(os.getpid())
    )
    seed = hashlib.sha256(machine_id.encode()).digest()
    return base64.urlsafe_b64encode(seed)


def get_fernet() -> Fernet:
    key = _get_machine_key()
    return Fernet(key)


def encrypt_value(value: str) -> str:
    f = get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    f = get_fernet()
    return f.decrypt(encrypted.encode()).decode()


# Supported file types
SUPPORTED_EXTENSIONS = {
    "pdf": "PDF",
    "docx": "DOCX",
    "doc": "DOC",
    "xlsx": "XLSX",
    "xls": "XLS",
    "png": "PNG",
    "jpg": "JPG",
    "jpeg": "JPEG",
    "tiff": "TIFF",
    "tif": "TIFF",
    "bmp": "BMP",
    "csv": "CSV",
    "txt": "TXT",
}

SKIP_PATTERNS = {
    "~$",  # Office temp files
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}

# LLM Models with metadata
# For Azure, these model IDs are used as the default deployment name suggestion.
# The user can override the deployment name in Settings.
LLM_MODELS = {
    # ── OpenAI (direct) ──────────────────────────────────────────
    "gpt-4o": {
        "name": "GPT-4o",
        "provider": "openai",
        "speed": "Fast",
        "cost_per_1k_tokens": 0.005,
        "context_window": 128000,
        "recommended": True,
    },
    "gpt-4o-mini": {
        "name": "GPT-4o Mini",
        "provider": "openai",
        "speed": "Very Fast",
        "cost_per_1k_tokens": 0.00015,
        "context_window": 128000,
        "recommended": False,
    },
    "gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "provider": "openai",
        "speed": "Fastest",
        "cost_per_1k_tokens": 0.0005,
        "context_window": 16384,
        "recommended": False,
    },
    # ── Azure OpenAI — deployment names are user-defined, these are
    #    the common default deployment names suggested in the UI ──
    "azure-gpt-4o": {
        "name": "Azure GPT-4o",
        "provider": "azure",
        "speed": "Fast",
        "cost_per_1k_tokens": 0.005,
        "context_window": 128000,
        "recommended": True,
        "default_deployment": "gpt-4o",
    },
    "azure-gpt-4o-mini": {
        "name": "Azure GPT-4o Mini",
        "provider": "azure",
        "speed": "Very Fast",
        "cost_per_1k_tokens": 0.00015,
        "context_window": 128000,
        "recommended": False,
        "default_deployment": "gpt-4o-mini",
    },
    # ── Ollama (local) — served via Ollama's OpenAI-compatible API ──
    # Model names must match exactly what is installed: `ollama list`
    "qwen2.5:7b": {
        "name": "Qwen 2.5 7B",
        "provider": "ollama",
        "speed": "Fast (local)",
        "cost_per_1k_tokens": 0.0,
        "context_window": 32768,
        "recommended": True,
    },
    "qwen2.5:14b": {
        "name": "Qwen 2.5 14B",
        "provider": "ollama",
        "speed": "Medium (local)",
        "cost_per_1k_tokens": 0.0,
        "context_window": 32768,
        "recommended": False,
    },
    "qwen2.5:32b": {
        "name": "Qwen 2.5 32B",
        "provider": "ollama",
        "speed": "Slow (local)",
        "cost_per_1k_tokens": 0.0,
        "context_window": 32768,
        "recommended": False,
    },
    "qwen2.5-coder:7b": {
        "name": "Qwen 2.5 Coder 7B",
        "provider": "ollama",
        "speed": "Fast (local)",
        "cost_per_1k_tokens": 0.0,
        "context_window": 32768,
        "recommended": False,
    },
    "llama3.2:3b": {
        "name": "Llama 3.2 3B",
        "provider": "ollama",
        "speed": "Very Fast (local)",
        "cost_per_1k_tokens": 0.0,
        "context_window": 8192,
        "recommended": False,
    },
    "llama3.1:8b": {
        "name": "Llama 3.1 8B",
        "provider": "ollama",
        "speed": "Fast (local)",
        "cost_per_1k_tokens": 0.0,
        "context_window": 131072,
        "recommended": False,
    },
    "mistral:7b": {
        "name": "Mistral 7B",
        "provider": "ollama",
        "speed": "Fast (local)",
        "cost_per_1k_tokens": 0.0,
        "context_window": 32768,
        "recommended": False,
    },
}

# Default Azure OpenAI API version
AZURE_OPENAI_API_VERSION = "2024-10-21"

# Default Ollama base URL (Ollama's default listen address)
OLLAMA_BASE_URL = "http://localhost:11434"

# Estimated tokens per file type
ESTIMATED_TOKENS_PER_FILE = {
    "PDF": 2000,
    "DOCX": 1500,
    "XLSX": 1000,
    "XLS": 1000,
    "PNG": 500,
    "JPG": 500,
    "JPEG": 500,
    "TIFF": 500,
    "BMP": 500,
    "CSV": 800,
    "TXT": 1000,
}

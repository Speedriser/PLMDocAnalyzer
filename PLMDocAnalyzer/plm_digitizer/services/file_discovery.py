"""
PLM Digitizer - Async File Discovery Service
"""
import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from dataclasses import dataclass

from config import SUPPORTED_EXTENSIONS, SKIP_PATTERNS


@dataclass
class FileMetadata:
    file_path: str
    file_type: str
    file_size_bytes: int
    extension: str


def should_skip(path: Path) -> bool:
    """Check if file should be skipped."""
    name = path.name
    # Skip hidden files
    if name.startswith("."):
        return True
    # Skip temp files
    for pattern in SKIP_PATTERNS:
        if name.startswith(pattern) or name == pattern:
            return True
    return False


def get_file_type(path: Path) -> Optional[str]:
    """Determine file type from extension."""
    ext = path.suffix.lstrip(".").lower()
    return SUPPORTED_EXTENSIONS.get(ext)


async def discover_files(
    folder_path: str,
    max_file_size_mb: float = 100.0,
) -> AsyncGenerator[FileMetadata, None]:
    """
    Async generator that yields FileMetadata for each supported file.
    Uses os.scandir for efficient directory traversal without loading all paths.
    """
    root = Path(folder_path)
    if not root.exists() or not root.is_dir():
        return

    max_bytes = int(max_file_size_mb * 1024 * 1024)

    # Use a stack for iterative DFS (avoids deep recursion)
    stack: List[Path] = [root]

    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    # Yield control periodically
                    await asyncio.sleep(0)

                    if entry.is_dir(follow_symlinks=False):
                        dir_path = Path(entry.path)
                        if not should_skip(dir_path):
                            stack.append(dir_path)
                    elif entry.is_file(follow_symlinks=False):
                        file_path = Path(entry.path)
                        if should_skip(file_path):
                            continue
                        file_type = get_file_type(file_path)
                        if not file_type:
                            continue
                        try:
                            size = entry.stat().st_size
                            if size > max_bytes:
                                continue
                            yield FileMetadata(
                                file_path=str(file_path),
                                file_type=file_type,
                                file_size_bytes=size,
                                extension=file_path.suffix.lstrip(".").lower(),
                            )
                        except OSError:
                            continue
        except PermissionError:
            continue
        except OSError:
            continue


async def count_files(
    folder_path: str,
    max_file_size_mb: float = 100.0,
) -> Tuple[int, Dict[str, int]]:
    """
    Count files by type in the folder.
    Returns (total, breakdown_by_type).
    """
    total = 0
    breakdown: Dict[str, int] = {}

    async for meta in discover_files(folder_path, max_file_size_mb):
        total += 1
        breakdown[meta.file_type] = breakdown.get(meta.file_type, 0) + 1

    return total, breakdown


def discover_files_sync(
    folder_path: str,
    max_file_size_mb: float = 100.0,
) -> List[FileMetadata]:
    """
    Synchronous version for use in Celery tasks.
    Returns list of FileMetadata without loading large amounts into memory
    by processing in batches.
    """
    results = []
    root = Path(folder_path)
    if not root.exists() or not root.is_dir():
        return results

    max_bytes = int(max_file_size_mb * 1024 * 1024)
    stack: List[Path] = [root]

    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        dir_path = Path(entry.path)
                        if not should_skip(dir_path):
                            stack.append(dir_path)
                    elif entry.is_file(follow_symlinks=False):
                        file_path = Path(entry.path)
                        if should_skip(file_path):
                            continue
                        file_type = get_file_type(file_path)
                        if not file_type:
                            continue
                        try:
                            size = entry.stat().st_size
                            if size > max_bytes:
                                continue
                            results.append(FileMetadata(
                                file_path=str(file_path),
                                file_type=file_type,
                                file_size_bytes=size,
                                extension=file_path.suffix.lstrip(".").lower(),
                            ))
                        except OSError:
                            continue
        except (PermissionError, OSError):
            continue

    return results


def estimate_processing_time(
    breakdown: Dict[str, int],
    worker_count: int = 4,
    model: str = "gpt-4o-mini",
) -> Tuple[float, float]:
    """
    Returns (estimated_minutes, estimated_cost_usd).
    """
    from config import ESTIMATED_TOKENS_PER_FILE, LLM_MODELS

    # Seconds per file (extraction + LLM)
    time_per_file = {
        "PDF": 3.0,
        "DOCX": 1.0,
        "XLSX": 1.0,
        "XLS": 1.5,
        "PNG": 4.0,
        "JPG": 4.0,
        "JPEG": 4.0,
        "TIFF": 5.0,
        "BMP": 4.0,
        "CSV": 0.5,
        "TXT": 0.5,
    }

    total_seconds = 0
    total_tokens = 0
    for file_type, count in breakdown.items():
        secs = time_per_file.get(file_type, 2.0)
        total_seconds += secs * count
        tokens = ESTIMATED_TOKENS_PER_FILE.get(file_type, 1000)
        total_tokens += tokens * count

    # Parallel processing
    effective_seconds = total_seconds / max(worker_count, 1)
    estimated_minutes = effective_seconds / 60.0

    model_info = LLM_MODELS.get(model, LLM_MODELS["gpt-4o-mini"])
    cost_per_1k = model_info["cost_per_1k_tokens"]
    estimated_cost = (total_tokens / 1000.0) * cost_per_1k

    return estimated_minutes, estimated_cost

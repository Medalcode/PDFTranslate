from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-Linux fallback
    fcntl = None

from app.paths import project_path


JOBS_DB: Path = project_path("data", "jobs.json")
LOCK_FILE: Path = JOBS_DB.with_suffix(".lock")
_THREAD_LOCK = threading.Lock()


def _read_all_unlocked() -> dict[str, dict[str, Any]]:
    if not JOBS_DB.exists():
        return {}
    try:
        return json.loads(JOBS_DB.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_all_unlocked(data: dict[str, dict[str, Any]]) -> None:
    JOBS_DB.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = JOBS_DB.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(tmp_path, JOBS_DB)


@contextmanager
def _exclusive_lock():
    JOBS_DB.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = LOCK_FILE.open("a+", encoding="utf-8")
    try:
        with _THREAD_LOCK:
            if fcntl is not None:
                fcntl.flock(lock_handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_handle, fcntl.LOCK_UN)
    finally:
        lock_handle.close()


def ensure_job(job_id: str, **fields: Any) -> dict[str, Any]:
    with _exclusive_lock():
        data = _read_all_unlocked()
        job = data.get(job_id, {})
        job.update(fields)
        data[job_id] = job
        _write_all_unlocked(data)
        return dict(job)


def update_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    with _exclusive_lock():
        data = _read_all_unlocked()
        if job_id not in data:
            return None
        data[job_id].update(fields)
        _write_all_unlocked(data)
        return dict(data[job_id])


def get_job(job_id: str) -> dict[str, Any] | None:
    with _exclusive_lock():
        data = _read_all_unlocked()
        job = data.get(job_id)
        return dict(job) if job else None
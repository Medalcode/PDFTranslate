import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from app.paths import project_path

logger = logging.getLogger(__name__)
JOBS_DB = project_path("data", "jobs.db")

def init_job_store():
    JOBS_DB.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(JOBS_DB)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error("Failed to initialize job store: %s", e)

# Initialize on import
init_job_store()

def ensure_job(job_id: str, **fields: Any) -> dict[str, Any]:
    try:
        with sqlite3.connect(str(JOBS_DB)) as conn:
            # Check if job exists
            res = conn.execute("SELECT data FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            job_data = json.loads(res[0]) if res else {}

            job_data.update(fields)
            conn.execute(
                "INSERT OR REPLACE INTO jobs (job_id, data) VALUES (?, ?)",
                (job_id, json.dumps(job_data))
            )
            conn.commit()
            return job_data
    except Exception as e:
        logger.error("Failed to ensure job %s: %s", job_id, e)
        return fields

def update_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(str(JOBS_DB)) as conn:
            res = conn.execute("SELECT data FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not res:
                return None

            job_data = json.loads(res[0])
            job_data.update(fields)

            conn.execute(
                "UPDATE jobs SET data = ? WHERE job_id = ?",
                (json.dumps(job_data), job_id)
            )
            conn.commit()
            return job_data
    except Exception as e:
        logger.error("Failed to update job %s: %s", job_id, e)
        return None

def get_job(job_id: str) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(str(JOBS_DB)) as conn:
            res = conn.execute("SELECT data FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if res:
                return json.loads(res[0])
            return None
    except Exception as e:
        logger.error("Failed to get job %s: %s", job_id, e)
        return None

def mark_zombie_jobs():
    """Mark jobs that were left in 'processing' state from a previous run as 'error'."""
    try:
        with sqlite3.connect(str(JOBS_DB)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id, data FROM jobs")
            rows = cursor.fetchall()
            for job_id, data_str in rows:
                data = json.loads(data_str)
                if data.get("status") == "processing":
                    data["status"] = "error"
                    data["error"] = "Interrupted by server restart"
                    data["phase"] = "error"
                    cursor.execute(
                        "UPDATE jobs SET data = ? WHERE job_id = ?",
                        (json.dumps(data), job_id)
                    )
            conn.commit()
    except Exception as e:
        logger.error("Failed to mark zombie jobs: %s", e)

def cleanup_old_jobs(hours: int = 24):
    """Delete jobs older than `hours`."""
    from app.config import UPLOAD_DIR

    try:
        with sqlite3.connect(str(JOBS_DB)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT job_id, data FROM jobs WHERE created_at < datetime('now', ?)",
                (f"-{hours} hours",)
            )
            rows = cursor.fetchall()
            for job_id, data_str in rows:
                data = json.loads(data_str)

                # Try to delete input file
                input_path = Path(UPLOAD_DIR) / f"{job_id}.pdf"
                if input_path.exists():
                    input_path.unlink(missing_ok=True)

                # Try to delete output file
                output_path = data.get("output_path")
                if output_path and Path(output_path).exists():
                    Path(output_path).unlink(missing_ok=True)

                # Delete from DB
                cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            conn.commit()
            if rows:
                logger.info("Cleaned up %d old jobs (older than %d hours).", len(rows), hours)
    except Exception as e:
        logger.error("Failed to cleanup old jobs: %s", e)

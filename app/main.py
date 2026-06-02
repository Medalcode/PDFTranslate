"""
FastAPI application for PDFTranslate.
Routes: POST /translate, GET /status/{job_id}, GET /download/{job_id}, GET /
"""

import logging
import shutil
import uuid
from enum import Enum
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from contextlib import asynccontextmanager

from app.config import OUTPUT_DIR, SOURCE_LANG, TARGET_LANG, UPLOAD_DIR
from app.job_store import ensure_job, get_job, update_job, mark_zombie_jobs, cleanup_old_jobs
from app.paths import project_path
from app.translator import translate_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def run_periodic_cleanup():
    while True:
        await asyncio.sleep(3600)  # Run cleanup every hour
        cleanup_old_jobs(24)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up PDFTranslate server... running initial maintenance.")
    mark_zombie_jobs()
    cleanup_old_jobs(24)
    task = asyncio.create_task(run_periodic_cleanup())
    yield
    task.cancel()

app = FastAPI(
    title="PDFTranslate",
    description="AI-powered PDF translator that preserves original layout.",
    version="1.0.0",
    lifespan=lifespan
)

# ── Static files ────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(project_path("static"))), name="static")


# ── Job state store ──────────────────────────────────────────────────────────
class JobStatus(str, Enum):
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


# ── Background worker ─────────────────────────────────────────────────────────
def _run_translation(job_id: str, input_path: str, output_path: str, source: str, target: str):
    logger.info("Job %s started (src=%s → tgt=%s)", job_id, source, target)

    # Progress callback persists state so any worker can report status.
    def progress_cb(phase, current, total):
        update_job(
            job_id,
            status=JobStatus.PROCESSING,
            phase=phase,
            current=current,
            total=total,
        )

    try:
        translate_pdf(
            input_path=input_path,
            output_path=output_path,
            source_lang=source,
            target_lang=target,
            progress_callback=progress_cb,
        )
        update_job(
            job_id,
            status=JobStatus.DONE,
            phase="done",
            current=100,
            total=100,
            error=None,
        )
        logger.info("Job %s completed → %s", job_id, output_path)
    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        update_job(
            job_id,
            status=JobStatus.ERROR,
            phase="error",
            current=0,
            total=0,
            error=str(exc),
        )


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = project_path("static", "index.html")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/translate")
async def translate(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_lang: str = SOURCE_LANG,
    target_lang: str = TARGET_LANG,
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    job_id = str(uuid.uuid4())
    input_path = str(Path(UPLOAD_DIR) / f"{job_id}.pdf")
    output_path = str(Path(OUTPUT_DIR) / f"{job_id}_translated.pdf")

    # Save uploaded file
    with open(input_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    # Register job
    ensure_job(
        job_id,
        status=JobStatus.PROCESSING,
        phase="queued",
        current=0,
        total=0,
        output_path=output_path,
        error=None,
        filename=file.filename,
        source_lang=source_lang,
        target_lang=target_lang,
    )

    # Start background translation
    background_tasks.add_task(
        _run_translation, job_id, input_path, output_path, source_lang, target_lang
    )

    return {
        "job_id": job_id,
        "status": JobStatus.PROCESSING,
        "message": "Translation started. Poll /status/{job_id} to check progress.",
    }


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "phase": job.get("phase"),
        "current": job.get("current", 0),
        "total": job.get("total", 0),
        "error": job.get("error"),
    }


@app.get("/download/{job_id}")
async def download(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != JobStatus.DONE:
        raise HTTPException(status_code=400, detail="Translation not ready yet.")
    output_path = job["output_path"]
    if not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found.")
    # Use original filename with _es suffix
    original = Path(job.get("filename", "document.pdf")).stem
    download_name = f"{original}_translated.pdf"
    return FileResponse(output_path, media_type="application/pdf", filename=download_name)

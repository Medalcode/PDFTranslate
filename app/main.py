"""
FastAPI application for PDFTranslate.
Routes: POST /translate, GET /status/{job_id}, GET /download/{job_id}, GET /
"""

import logging
import shutil
import uuid
from enum import Enum
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio

from app.config import OUTPUT_DIR, SOURCE_LANG, TARGET_LANG, UPLOAD_DIR
from app.translator import translate_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PDFTranslate",
    description="AI-powered PDF translator that preserves original layout.",
    version="1.0.0",
)

# ── Static files ────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Job state store (in-memory, sufficient for single-user local use) ────────
class JobStatus(str, Enum):
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


jobs: dict[str, dict] = {}  # job_id -> {status, output_path, error}


# ── Connection Manager for WebSockets ─────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)

    async def broadcast_progress(self, job_id: str, phase: str, current: int, total: int):
        if job_id in self.active_connections:
            message = {"type": "progress", "phase": phase, "current": current, "total": total}
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()


# ── Background worker ─────────────────────────────────────────────────────────
def _run_translation(job_id: str, input_path: str, output_path: str, source: str, target: str):
    logger.info("Job %s started (src=%s → tgt=%s)", job_id, source, target)
    
    # Progress callback that broadcasts to WebSocket
    def progress_cb(phase, current, total):
        # We need to bridge thread -> asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.broadcast_progress(job_id, phase, current, total))
        loop.close()

    try:
        translate_pdf(
            input_path=input_path,
            output_path=output_path,
            source_lang=source,
            target_lang=target,
            progress_callback=progress_cb
        )
        jobs[job_id]["status"] = JobStatus.DONE
        logger.info("Job %s completed → %s", job_id, output_path)
        # Notify completion
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.broadcast_progress(job_id, "done", 100, 100))
        loop.close()
    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        jobs[job_id]["status"] = JobStatus.ERROR
        jobs[job_id]["error"] = str(exc)
        # Notify error
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.broadcast_progress(job_id, "error", 0, 0))
        loop.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path("static/index.html")
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
    jobs[job_id] = {
        "status": JobStatus.PROCESSING,
        "output_path": output_path,
        "error": None,
        "filename": file.filename,
    }

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
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "error": job.get("error"),
    }


@app.get("/download/{job_id}")
async def download(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = jobs[job_id]
    if job["status"] != JobStatus.DONE:
        raise HTTPException(status_code=400, detail="Translation not ready yet.")
    output_path = job["output_path"]
    if not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found.")
    # Use original filename with _es suffix
    original = Path(job.get("filename", "document.pdf")).stem
    download_name = f"{original}_translated.pdf"
    return FileResponse(output_path, media_type="application/pdf", filename=download_name)


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(websocket, job_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)

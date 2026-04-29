from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "PDFTranslate" in response.text


def test_config():
    from app.config import OUTPUT_DIR, UPLOAD_DIR

    assert Path(UPLOAD_DIR).is_absolute()
    assert Path(OUTPUT_DIR).is_absolute()


def test_job_store_roundtrip(tmp_path, monkeypatch):
    from app import job_store

    monkeypatch.setattr(job_store, "JOBS_DB", tmp_path / "jobs.json")
    monkeypatch.setattr(job_store, "LOCK_FILE", tmp_path / "jobs.lock")

    job_store.ensure_job("job-1", status="processing", phase="queued", current=0, total=0)
    job_store.update_job("job-1", phase="extract", current=2, total=5)

    job = job_store.get_job("job-1")
    assert job is not None
    assert job["phase"] == "extract"
    assert job["current"] == 2
    assert job["total"] == 5


def test_llm_prompt_uses_configured_languages(monkeypatch):
    from app import translator

    captured = {}

    class DummyLLM:
        def call(self, prompt: str) -> str:
            captured["prompt"] = prompt
            return "[1] Bonjour"

    monkeypatch.setattr(translator, "get_cached_translation", lambda text, target_lang: None)
    monkeypatch.setattr(translator, "save_to_cache", lambda *args, **kwargs: None)

    result = translator._translate_with_llm(["Hello"], DummyLLM(), "en", "fr")
    assert result == ["Bonjour"]
    assert "en to fr" in captured["prompt"]

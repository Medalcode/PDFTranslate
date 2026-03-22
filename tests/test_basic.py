import pytest
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "PDFTranslate" in response.text

def test_config():
    from app.config import UPLOAD_DIR, OUTPUT_DIR
    assert "data/uploads" in UPLOAD_DIR
    assert "data/outputs" in OUTPUT_DIR

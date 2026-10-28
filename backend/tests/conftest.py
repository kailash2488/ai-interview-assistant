import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="aia-tests-"))
os.environ["AIA_DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["AIA_UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ["AIA_QDRANT_PATH"] = ":memory:"
os.environ["AIA_SECRET_KEY_PATH"] = str(_tmp / "secret.key")
os.environ["AIA_RUNTIME_SETTINGS_PATH"] = str(_tmp / "llm_settings.json")
# Developer .env choices must never change test behavior.
os.environ["AIA_LLM_PROVIDER"] = "ollama"
os.environ["AIA_ENABLE_OLLAMA"] = "true"
os.environ.pop("AIA_GEMINI_API_KEY", None)

import fitz  # noqa: E402
import pytest  # noqa: E402
from docx import Document as DocxDocument  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.vectorstore import COLLECTION, get_client  # noqa: E402


USER = {"email": "tester@example.com", "name": "Tester", "password": "correct horse battery"}
OTHER = {"email": "other@example.com", "name": "Other Person", "password": "another long password"}


def _reset() -> None:
    from app.api import auth

    Base.metadata.drop_all(engine)
    store = get_client()
    if store.collection_exists(COLLECTION):
        store.delete_collection(COLLECTION)
    auth._failures.clear()


@pytest.fixture()
def anon_client():
    """A browser that is not signed in (empty database)."""
    _reset()
    with TestClient(app) as c:  # lifespan creates tables
        yield c


@pytest.fixture()
def client(anon_client):
    """A signed-in browser for the default test user: the session cookie is kept by the test client."""
    r = anon_client.post("/auth/signup", json=USER)
    assert r.status_code == 201, r.text
    return anon_client


@pytest.fixture()
def other_client(client):
    """A second signed-in user in the same database, to prove accounts cannot see each other's data."""
    with TestClient(app) as c:
        r = c.post("/auth/signup", json=OTHER)
        assert r.status_code == 201, r.text
        yield c


def make_pdf(path: Path, text: str, pages: int = 1, header: str | None = None) -> Path:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        if header:
            page.insert_text((50, 30), header, fontsize=9)
        page.insert_text((50, 60), text, fontsize=10)
        page.insert_text((280, 820), str(i + 1), fontsize=9)
    doc.save(path)
    doc.close()
    return path


def make_docx(path: Path, text: str) -> Path:
    d = DocxDocument()
    for line in text.split("\n"):
        d.add_paragraph(line)
    d.save(path)
    return path


@pytest.fixture()
def tmp_files(tmp_path):
    return tmp_path

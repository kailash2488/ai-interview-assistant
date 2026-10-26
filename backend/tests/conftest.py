import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="aia-tests-"))
os.environ["AIA_DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["AIA_UPLOAD_DIR"] = str(_tmp / "uploads")

import fitz  # noqa: E402
import pytest  # noqa: E402
from docx import Document as DocxDocument  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # lifespan creates tables
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

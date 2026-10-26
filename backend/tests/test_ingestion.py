import pytest

from app.services.ingestion.cleaner import clean_pages
from app.services.ingestion.parsers import ParseError, extract_pages, validate_signature
from app.services.ingestion.pipeline import process_text
from app.services.ingestion.sectioner import split_sections
from tests.conftest import make_docx, make_pdf
from tests.samples import RESUMES

EXPECTED_SECTIONS = {
    "backend_dev": {"summary", "experience", "projects", "skills", "education"},
    "ml_engineer": {"summary", "experience", "skills", "education", "certifications"},
    "fresher": {"summary", "education", "projects", "skills", "achievements"},
    "devops": {"experience", "skills", "education"},
    "no_headings": {"full_text"},
}


def _extract(tmp_path, name, fmt):
    text = RESUMES[name]
    if fmt == "pdf":
        path = make_pdf(tmp_path / f"{name}.pdf", text)
    elif fmt == "docx":
        path = make_docx(tmp_path / f"{name}.docx", text)
    else:
        path = tmp_path / f"{name}.txt"
        path.write_text(text, encoding="utf-8")
    return process_text(extract_pages(path))


@pytest.mark.parametrize("fmt", ["pdf", "docx", "txt"])
@pytest.mark.parametrize("name", list(RESUMES))
def test_parse_resume_formats(tmp_path, name, fmt):
    text, sections = _extract(tmp_path, name, fmt)
    first_line = RESUMES[name].strip().split("\n")[0].strip()
    assert first_line.split()[0] in text  # content survived
    assert "•" not in text  # bullets normalised
    found = {s["name"] for s in sections}
    if fmt != "pdf":  # insert_text in the PDF fixture doesn't wrap, so headings can shift; check docx/txt strictly
        assert EXPECTED_SECTIONS[name] <= found | {"header"}


def test_pdf_pymupdf_sections_detected(tmp_path):
    text, sections = _extract(tmp_path, "backend_dev", "pdf")
    assert "Python" in text and sections


def test_cleaner_removes_repeated_headers_and_page_numbers():
    pages = [f"Jane Doe - Resume\nBody line {i}\n{i + 1}" for i in range(4)]
    out = clean_pages(pages)
    assert "Jane Doe - Resume" not in out
    assert "Body line 2" in out
    assert "\n3\n" not in f"\n{out}\n"


def test_cleaner_normalises_whitespace_bullets_ligatures():
    out = clean_pages(["•   Built   ﬁne tools\r\n\r\n\r\n\r\n● Shipped"])
    assert out == "- Built fine tools\n\n- Shipped"


def test_sectioner_headings_with_colons_and_case():
    sections = split_sections("Name\nTECHNICAL SKILLS:\nPython\nWork Experience\nAcme")
    assert [s["name"] for s in sections] == ["header", "skills", "experience"]


def test_sectioner_no_headings_returns_full_text():
    assert split_sections("just some prose") == [{"name": "full_text", "text": "just some prose"}]


def test_pdf_scanned_or_empty_is_rejected(tmp_path):
    import fitz

    doc = fitz.open()
    doc.new_page()
    path = tmp_path / "blank.pdf"
    doc.save(path)
    with pytest.raises(ParseError, match="No extractable text"):
        extract_pages(path)


def test_txt_latin1_fallback(tmp_path):
    path = tmp_path / "r.txt"
    path.write_bytes("Café résumé".encode("latin-1"))
    assert extract_pages(path) == ["Café résumé"]


def test_signature_validation():
    validate_signature(".pdf", b"%PDF-1.7")
    with pytest.raises(ParseError):
        validate_signature(".pdf", b"hello")
    with pytest.raises(ParseError):
        validate_signature(".docx", b"hello")
    with pytest.raises(ParseError):
        validate_signature(".txt", b"ab\x00cd")

import json

import httpx
import pytest

from app.services.ingestion import parsers
from app.services.ingestion.parsers import ParseError, extract_pages
from app.services.llm.client import LLMError, LLMUnavailable, OllamaClient

LONG = "This resume text is comfortably longer than the fifty character minimum for a PDF. " * 2


# ---------- parsers: fallbacks and failures ----------

def test_pdf_falls_back_to_pdfplumber_when_pymupdf_finds_little(tmp_path, monkeypatch):
    monkeypatch.setattr(parsers, "_parse_pdf_pymupdf", lambda p: ["  "])
    monkeypatch.setattr(parsers, "_parse_pdf_pdfplumber", lambda p: [LONG])
    assert parsers.parse_pdf(tmp_path / "x.pdf") == [LONG]


def test_pdf_pymupdf_failure_uses_pdfplumber(tmp_path, monkeypatch):
    def boom(p):
        raise RuntimeError("corrupt")

    monkeypatch.setattr(parsers, "_parse_pdf_pymupdf", boom)
    monkeypatch.setattr(parsers, "_parse_pdf_pdfplumber", lambda p: [LONG])
    assert parsers.parse_pdf(tmp_path / "x.pdf") == [LONG]


def test_pdf_unreadable_by_both_parsers(tmp_path, monkeypatch):
    def boom(p):
        raise RuntimeError("corrupt")

    monkeypatch.setattr(parsers, "_parse_pdf_pymupdf", boom)
    monkeypatch.setattr(parsers, "_parse_pdf_pdfplumber", boom)
    with pytest.raises(ParseError, match="Could not read PDF"):
        parsers.parse_pdf(tmp_path / "x.pdf")


def test_pdf_keeps_pymupdf_text_when_fallback_is_worse(tmp_path, monkeypatch):
    monkeypatch.setattr(parsers, "_parse_pdf_pymupdf", lambda p: ["short"])
    monkeypatch.setattr(parsers, "_parse_pdf_pdfplumber", lambda p: [""])
    with pytest.raises(ParseError, match="No extractable text"):
        parsers.parse_pdf(tmp_path / "x.pdf")


def test_corrupt_docx_and_unsupported_extension(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"PK this is not really a zip archive")
    with pytest.raises(ParseError, match="Could not read DOCX"):
        extract_pages(bad)
    other = tmp_path / "x.rtf"
    other.write_text("hi")
    with pytest.raises(ParseError, match="Unsupported"):
        extract_pages(other)


def test_docx_tables_are_included(tmp_path):
    from docx import Document

    doc = Document()
    doc.add_paragraph("Skills")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Python"
    table.rows[0].cells[1].text = "Expert"
    path = tmp_path / "t.docx"
    doc.save(path)
    assert "Python | Expert" in extract_pages(path)[0]


def test_utf16_text_is_decoded(tmp_path):
    path = tmp_path / "u.txt"
    path.write_bytes("Résumé naïve".encode("utf-16"))
    assert extract_pages(path) == ["Résumé naïve"]


# ---------- Ollama streaming ----------

class FakeStream:
    def __init__(self, lines, status=200):
        self.lines, self.status_code = lines, status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_lines(self):
        return iter(self.lines)


def chunk(text, done=False):
    return json.dumps({"message": {"content": text}, "done": done})


def test_ollama_stream_yields_pieces_and_stops_at_done(monkeypatch):
    captured = {}

    def fake(method, url, json=None, timeout=None):
        captured.update(url=url, json=json)
        return FakeStream([chunk("How "), "", chunk("do you test?"), chunk("", done=True), chunk("IGNORED")])

    monkeypatch.setattr(httpx, "stream", fake)
    out = "".join(OllamaClient("http://o:11434").stream_text(system="s", user="u", max_tokens=90))
    assert out == "How do you test?"
    assert captured["url"] == "http://o:11434/api/chat" and captured["json"]["stream"] is True
    assert captured["json"]["options"]["num_predict"] == 90


@pytest.mark.parametrize("status, match", [(404, "ollama pull"), (500, "HTTP 500")])
def test_ollama_stream_http_errors(monkeypatch, status, match):
    monkeypatch.setattr(httpx, "stream", lambda *a, **k: FakeStream([], status))
    with pytest.raises(LLMError, match=match):
        list(OllamaClient().stream_text(system="s", user="u"))


def test_ollama_stream_connection_problems(monkeypatch):
    def refuse(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "stream", refuse)
    with pytest.raises(LLMUnavailable, match="Cannot reach Ollama"):
        list(OllamaClient().stream_text(system="s", user="u"))

    def slow(*a, **k):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "stream", slow)
    with pytest.raises(LLMUnavailable, match="too long"):
        list(OllamaClient().stream_text(system="s", user="u"))


def test_ollama_generic_http_error_on_chat(monkeypatch):
    res = httpx.Response(500, text="boom", request=httpx.Request("POST", "http://x"))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: res)
    with pytest.raises(LLMError, match="HTTP 500"):
        OllamaClient().embed(["x"])

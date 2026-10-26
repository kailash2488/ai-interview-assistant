import logging
from pathlib import Path

from app.core.db import SessionLocal
from app.models import Document
from app.services.ingestion.cleaner import clean_pages
from app.services.ingestion.parsers import ParseError, extract_pages
from app.services.ingestion.sectioner import split_sections

log = logging.getLogger(__name__)


def process_text(pages: list[str]) -> tuple[str, list[dict[str, str]]]:
    text = clean_pages(pages)
    if not text:
        raise ParseError("Document contains no text")
    return text, split_sections(text)


def process_document(document_id: str) -> None:
    """Background task: parse -> clean -> section. Updates the document row's status."""
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        doc.status, doc.error = "parsing", None
        db.commit()
        try:
            text, sections = process_text(extract_pages(Path(doc.stored_path)))
            doc.raw_text, doc.sections_json, doc.status = text, sections, "ready"
        except ParseError as exc:
            doc.status, doc.error = "failed", str(exc)
        except Exception:
            log.exception("Unexpected error parsing document %s", document_id)
            doc.status, doc.error = "failed", "Unexpected error while parsing the file"
        db.commit()

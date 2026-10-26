import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.sessions import get_session_or_404
from app.core.config import settings
from app.core.db import get_db
from app.models import Document
from app.schemas.document import DocumentDetail, DocumentKind, DocumentOut
from app.services.ingestion.parsers import ALLOWED_EXTENSIONS, ParseError, validate_signature
from app.services import vectorstore
from app.services.ingestion.pipeline import process_document

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions/{session_id}/documents", tags=["documents"])

SINGLETON_KINDS = {DocumentKind.resume.value, DocumentKind.jd.value}


def _safe_name(filename: str | None) -> str:
    return Path(filename or "upload").name[:200] or "upload"


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    session_id: str,
    background: BackgroundTasks,
    kind: DocumentKind = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    get_session_or_404(session_id, db)
    filename = _safe_name(file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")
    try:
        validate_signature(ext, data[:1024])
    except ParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    # A session has one resume and one JD: a new upload replaces the old one.
    if kind.value in SINGLETON_KINDS:
        for old in db.scalars(select(Document).where(Document.session_id == session_id, Document.kind == kind.value)):
            Path(old.stored_path).unlink(missing_ok=True)
            db.delete(old)

    dest_dir = settings.upload_dir / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{ext}"
    dest.write_bytes(data)

    doc = Document(session_id=session_id, kind=kind.value, filename=filename, stored_path=str(dest))
    db.add(doc)
    db.commit()
    background.add_task(process_document, doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(session_id: str, db: Session = Depends(get_db)):
    get_session_or_404(session_id, db)
    return db.scalars(select(Document).where(Document.session_id == session_id).order_by(Document.created_at)).all()


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(session_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None or doc.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(session_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None or doc.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    Path(doc.stored_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    try:
        vectorstore.delete_document(document_id)
    except Exception:
        log.warning("Could not delete vectors for document %s", document_id, exc_info=True)

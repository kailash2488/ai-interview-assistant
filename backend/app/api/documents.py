import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.sessions import get_session_or_404
from app.core.config import settings
from app.core.db import get_db
from app.models import Document, InterviewSession, User
from app.schemas.document import DocumentDetail, DocumentKind, DocumentOut
from app.services.ingestion.parsers import ALLOWED_EXTENSIONS, ParseError, validate_signature
from app.services import vectorstore
from app.services.ingestion.pipeline import process_document

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions/{session_id}/documents", tags=["documents"])

SINGLETON_KINDS = {DocumentKind.resume.value, DocumentKind.jd.value}


class ReusableDocument(BaseModel):
    id: str
    filename: str
    session_title: str
    kind: str


class ReuseIn(BaseModel):
    document_id: str


def _reset_analysis(db: Session, session) -> None:
    """The resume or JD changed, so the analysis and plan built from it are stale. Remove them; the user re-analyses."""
    if session.questions:
        raise HTTPException(status.HTTP_409_CONFLICT, "The interview has already started. Start a new interview to use different documents.")
    if session.analysis is not None or session.plan is not None:
        session.analysis = None
        session.plan = None
        session.status = "created"
        try:
            vectorstore.delete_session(session.id)
        except Exception:
            log.warning("Could not clear vectors for session %s", session.id, exc_info=True)


def _safe_name(filename: str | None) -> str:
    return Path(filename or "upload").name[:200] or "upload"


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    session_id: str,
    background: BackgroundTasks,
    kind: DocumentKind = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    session = get_session_or_404(session_id, db, user)
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

    if kind is DocumentKind.other:
        extra = sum(1 for d in session.documents if d.kind == "other")
        if extra >= settings.max_other_documents:
            raise HTTPException(status.HTTP_409_CONFLICT, f"At most {settings.max_other_documents} extra documents per interview")
    else:
        _reset_analysis(db, session)

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
def list_documents(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    get_session_or_404(session_id, db, user)
    return db.scalars(select(Document).where(Document.session_id == session_id).order_by(Document.created_at)).all()


@router.get("/reuse-options", response_model=list[ReusableDocument])
def reuse_options(session_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    get_session_or_404(session_id, db, user)
    rows = db.execute(select(Document, InterviewSession).join(
        InterviewSession, Document.session_id == InterviewSession.id
    ).where(InterviewSession.user_id == user.id, Document.session_id != session_id,
            Document.status == "ready", Document.kind.in_(("resume", "jd"))).order_by(Document.created_at.desc())).all()
    return [ReusableDocument(id=d.id, filename=d.filename, session_title=s.title, kind=d.kind) for d, s in rows]


@router.post("/reuse", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def reuse_document(session_id: str, payload: ReuseIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = get_session_or_404(session_id, db, user)
    source = db.get(Document, payload.document_id)
    source_session = db.get(InterviewSession, source.session_id) if source else None
    if source is None or source_session is None or source_session.user_id != user.id or source.status != "ready" or source.kind not in SINGLETON_KINDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reusable document not found")
    _reset_analysis(db, session)
    for old in list(session.documents):
        if old.kind == source.kind:
            Path(old.stored_path).unlink(missing_ok=True); db.delete(old)
    dest_dir = settings.upload_dir / session_id; dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{uuid.uuid4().hex}{Path(source.filename).suffix.lower()}"
    try:
        shutil.copy2(source.stored_path, dest)
    except OSError:
        # A restored database may outlive its original upload. Reuse the parsed text without faking a PDF/DOCX.
        dest = dest.with_suffix(".txt")
        dest.write_text(source.raw_text or "", encoding="utf-8")
    doc = Document(session_id=session_id, kind=source.kind, filename=source.filename, stored_path=str(dest), status="ready", raw_text=source.raw_text, sections_json=source.sections_json)
    db.add(doc); db.commit(); return doc


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(session_id: str, document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    get_session_or_404(session_id, db, user)
    doc = db.get(Document, document_id)
    if doc is None or doc.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(session_id: str, document_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    session = get_session_or_404(session_id, db, user)
    doc = db.get(Document, document_id)
    if doc is None or doc.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if doc.kind in SINGLETON_KINDS:
        _reset_analysis(db, session)
    Path(doc.stored_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    try:
        vectorstore.delete_document(document_id)
    except Exception:
        log.warning("Could not delete vectors for document %s", document_id, exc_info=True)

import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Document, InterviewSession, SessionAnalysis
from app.schemas.analysis import CandidateProfile, JDRequirements
from app.services import vectorstore
from app.services.analysis.gap import analyse_gap
from app.services.llm.client import LLMError, get_llm
from app.services.llm.prompts import render, wrap_document

log = logging.getLogger(__name__)
MAX_DOC_CHARS = 12000  # keeps resume + JD comfortably inside the context window


def extract_profile(llm, resume_text: str) -> CandidateProfile:
    system, user = render("extract_profile.v1", document=wrap_document(resume_text[:MAX_DOC_CHARS]))
    return llm.chat_json(system=system, user=user, schema=CandidateProfile, model=settings.evaluator_model, temperature=0.0)


def extract_requirements(llm, jd_text: str) -> JDRequirements:
    system, user = render("extract_jd.v1", document=wrap_document(jd_text[:MAX_DOC_CHARS]))
    return llm.chat_json(system=system, user=user, schema=JDRequirements, model=settings.evaluator_model, temperature=0.0)


def _doc_text(docs: list[Document], kind: str) -> str:
    return next((d.raw_text or "" for d in docs if d.kind == kind and d.status == "ready"), "")


def run_analysis(session_id: str) -> None:
    """Background task. The caller has already created the 'running' row."""
    with SessionLocal() as db:
        row = db.scalar(select(SessionAnalysis).where(SessionAnalysis.session_id == session_id))
        if row is None:
            return
        docs = list(db.scalars(select(Document).where(Document.session_id == session_id, Document.status == "ready")))
        resume, jd = _doc_text(docs, "resume"), _doc_text(docs, "jd")
        indexable = [
            {"id": d.id, "kind": d.kind, "filename": d.filename, "sections": d.sections_json or []} for d in docs
        ]
        try:
            llm = get_llm()
            profile = extract_profile(llm, resume)
            requirements = extract_requirements(llm, jd)
            row.profile_json = profile.model_dump(mode="json")
            row.requirements_json = requirements.model_dump(mode="json")
            row.gap_json = analyse_gap(profile, requirements, resume).model_dump(mode="json")
            row.model, row.status, row.error = settings.evaluator_model, "ready", None
            warnings: list[str] = []
            try:
                vectorstore.index_session(session_id, indexable, llm)
            except Exception as exc:  # embeddings are an enhancement; analysis stays usable without them
                log.warning("Indexing failed for session %s: %s", session_id, exc)
                warnings.append(f"Documents were not indexed for retrieval: {exc}")
            row.warnings_json = warnings
            session = db.get(InterviewSession, session_id)
            if session:
                session.status = "analysed"
        except LLMError as exc:
            row.status, row.error = "failed", str(exc)
        except Exception:
            log.exception("Analysis crashed for session %s", session_id)
            row.status, row.error = "failed", "Unexpected error during analysis"
        db.commit()

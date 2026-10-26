"""Embedded Qdrant store for document chunks, filtered by session_id (one collection)."""
import logging
import uuid
from threading import Lock

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models

from app.core.config import settings
from app.services.llm.client import LLMClient

log = logging.getLogger(__name__)
COLLECTION = "document_chunks"
_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=150)
_client: QdrantClient | None = None
_lock = Lock()


def get_client() -> QdrantClient:
    global _client
    with _lock:
        if _client is None:
            _client = QdrantClient(":memory:") if settings.qdrant_path == ":memory:" else QdrantClient(path=settings.qdrant_path)
        return _client


def _ensure_collection(client: QdrantClient, dim: int) -> None:
    if not client.collection_exists(COLLECTION):
        client.create_collection(COLLECTION, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))


def make_chunks(sections: list[dict[str, str]]) -> list[tuple[str, str]]:
    """Section-level chunks; only sections longer than the splitter size are split further."""
    chunks: list[tuple[str, str]] = []
    for sec in sections:
        for piece in _splitter.split_text(sec["text"]):
            chunks.append((sec["name"], piece))
    return chunks


def _match(field: str, value: str) -> models.FieldCondition:
    return models.FieldCondition(key=field, match=models.MatchValue(value=value))


def delete_document(document_id: str) -> None:
    client = get_client()
    if client.collection_exists(COLLECTION):
        client.delete(COLLECTION, models.FilterSelector(filter=models.Filter(must=[_match("document_id", document_id)])))


def delete_session(session_id: str) -> None:
    client = get_client()
    if client.collection_exists(COLLECTION):
        client.delete(COLLECTION, models.FilterSelector(filter=models.Filter(must=[_match("session_id", session_id)])))


def index_session(session_id: str, docs: list[dict], llm: LLMClient) -> int:
    """docs: [{id, kind, filename, sections}]. Replaces all vectors for the session. Returns chunk count."""
    delete_session(session_id)
    records: list[tuple[dict, str]] = []
    for d in docs:
        for section, text in make_chunks(d["sections"]):
            records.append(({"session_id": session_id, "document_id": d["id"], "kind": d["kind"], "source": d["filename"], "section": section, "text": text}, text))
    if not records:
        return 0
    vectors = llm.embed([text for _, text in records])
    client = get_client()
    _ensure_collection(client, len(vectors[0]))
    client.upsert(
        COLLECTION,
        [models.PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload) for (payload, _), vec in zip(records, vectors)],
    )
    return len(records)


def search(session_id: str, query_vector: list[float], limit: int = 4, kind: str | None = None) -> list[dict]:
    client = get_client()
    if not client.collection_exists(COLLECTION):
        return []
    must = [_match("session_id", session_id)] + ([_match("kind", kind)] if kind else [])
    hits = client.query_points(COLLECTION, query=query_vector, query_filter=models.Filter(must=must), limit=limit).points
    return [{**h.payload, "score": h.score} for h in hits]

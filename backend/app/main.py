from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, auth, data, documents, history, interview, llm_settings, report, sessions
from app.core.config import settings
from app.core.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="AI Interview Assistant", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(interview.router)
app.include_router(llm_settings.router)
app.include_router(report.router)
app.include_router(history.router)
app.include_router(data.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}

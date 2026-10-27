from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analysis, documents, interview, llm_settings, sessions
from app.core.config import settings
from app.core.db import init_db
from app.services.llm import runtime


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    runtime.apply()
    yield


app = FastAPI(title="AI Interview Assistant", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(analysis.router)
app.include_router(interview.router)
app.include_router(llm_settings.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}

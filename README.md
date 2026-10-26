# AI Interview Assistant

An open-source, local-first web app for interview preparation. Upload a resume, a job description and any supporting documents. The app analyses them, runs a tailored mock interview, and produces a detailed feedback report.

Everything is free and runs on your own machine: FastAPI, React, SQLite, Qdrant and local LLMs through Ollama. No paid APIs, and your resume never leaves your computer.

The full plan is in [docs/SOP.pdf](docs/SOP.pdf).

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Planning, repository | Done |
| 1 | Foundation and document ingestion | Backend done; React upload screen pending |
| 2 | LLM analysis (Ollama, profile/JD extraction, gap analysis) | Not started |
| 3 | Interview plan and text interview | Not started |
| 4 | Feedback and report | Not started |
| 5 | History, polish, hardening | Not started |
| 6 | Voice mode (optional) | Not started |

## Backend quick start

```bash
cd backend
python -m venv ../env && source ../env/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload      # http://localhost:8000/docs
pytest
```

Or with Docker: `docker compose up --build`.

### What works now

- `POST /sessions`, `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`
- `POST /sessions/{id}/documents` (multipart: `kind` = resume | jd | other, and `file`), `GET` list and detail, `DELETE`
- PDF (PyMuPDF with pdfplumber fallback), DOCX and TXT parsing, cleaning and section detection
- Parsing runs in the background. Each document moves through `uploaded`, `parsing`, then `ready` or `failed`.

Settings come from environment variables prefixed `AIA_`, for example `AIA_MAX_UPLOAD_MB`.

## Licence

MIT

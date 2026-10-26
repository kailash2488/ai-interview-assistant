# AI Interview Assistant

An open-source, local-first web app for interview preparation. Upload a resume, a job description and any supporting documents. The app analyses them, runs a tailored mock interview, and produces a detailed feedback report.

Everything is free and runs on your own machine: FastAPI, React, SQLite, Qdrant and local LLMs through Ollama. No paid APIs, and your resume never leaves your computer.

The full plan is in [docs/SOP.pdf](docs/SOP.pdf).

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Planning, repository | Done |
| 1 | Foundation and document ingestion | Done |
| 2 | LLM analysis (Ollama, profile/JD extraction, gap analysis) | Built and working with mistral:7b; qwen2.5 comparison pending |
| 3 | Interview plan and text interview | Not started |
| 4 | Feedback and report | Not started |
| 5 | History, polish, hardening | Not started |
| 6 | Voice mode (optional) | Not started |

## Quick start

Run the backend and frontend in two terminals, then open http://localhost:5173.

### Backend

```bash
cd backend
python -m venv ../env && source ../env/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload      # http://localhost:8000/docs
pytest
```

Or with Docker: `docker compose up --build` (backend only for now).

### Frontend

Needs Node 20 or later.

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to the backend on port 8000
npm test
```

The repo includes `frontend/.npmrc` with `legacy-peer-deps=true`, which works around an npm 10 peer-dependency resolver crash.

### Ollama

```bash
ollama pull mistral:7b          # chat model used for extraction (change with AIA_EVALUATOR_MODEL)
ollama pull nomic-embed-text    # embedding model for document search
```

Analysis runs on your CPU and can take a few minutes. Compare models on your own machine with
`python backend/scripts/benchmark.py --models mistral:7b qwen2.5:7b`. It uses the samples in `data/samples/`
and writes results to `docs/benchmarks/`.

### What works now

- Web UI: create a session, run the analysis, review and correct the extracted skills and requirements, drag-and-drop or paste a resume, JD and extra documents, watch each file go Uploaded → Parsing → Ready, and view the extracted text and detected sections
- API:
  - `POST /sessions`, `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`
  - `POST /sessions/{id}/analyze` (starts profile, JD and gap analysis), `GET` and `PATCH /sessions/{id}/analysis`
  - `POST /sessions/{id}/documents` (multipart: `kind` = resume | jd | other, and `file`), `GET` list and detail, `DELETE`
- Parsing: PDF (PyMuPDF with pdfplumber fallback), DOCX and TXT parsing, cleaning and section detection
- Parsing runs in the background. Each document moves through `uploaded`, `parsing`, then `ready` or `failed`.

Settings come from environment variables prefixed `AIA_`, for example `AIA_MAX_UPLOAD_MB`.

## Licence

MIT

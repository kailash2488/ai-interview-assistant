# AI Interview Assistant

An open-source, local-first web app for interview preparation. Upload a resume, a job description and any supporting documents. The app analyses them, runs a tailored mock interview, and produces a detailed feedback report.

Everything is free and runs on your own machine: FastAPI, React, SQLite, Qdrant and local LLMs through Ollama. No paid APIs, and your resume never leaves your computer.

The full plan is in [docs/SOP.pdf](docs/SOP.pdf).

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Planning, repository | Done |
| 1 | Foundation and document ingestion | Done |
| 2 | LLM analysis (Ollama, profile/JD extraction, gap analysis) | Done (mistral:7b default; qwen2.5:7b benchmarked) |
| 3 | Interview plan and text interview | Done |
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

### How the interview works

The plan is built in plain code from the analysis (intro, core skills, project deep dives, gap areas, behavioural, your questions).
The model only writes the wording of each question and judges each answer. The code enforces the rules: a cap on follow-ups per topic
and overall (`question_count // 3`), no repeated questions, no scores shown, and a planned fallback question when the model's output
is unusable. `question_count` is the number of planned topics; follow-ups come on top.

### Model choice and speed

Benchmark on 8 sample documents (see `docs/benchmarks/`): `mistral:7b` 100% valid JSON, 88% skill recall, ~43 s per document;
`qwen2.5:7b` 100% valid JSON, 91% recall, ~60 s. The gap is small, so `mistral:7b` stays the default. Switch with
`AIA_INTERVIEWER_MODEL` and `AIA_EVALUATOR_MODEL`.

On a CPU-only laptop the interviewer answers within about 10-20 s after a short answer and about a minute after a long one, because each
answer is analysed to decide on follow-ups. A smaller interviewer model (for example `AIA_INTERVIEWER_MODEL=llama3.2:3b`) trades
some question quality for speed.

### What works now

- Web UI: create a session, run the analysis, review and correct the extracted skills and requirements, see the interview plan (topics only), and take the interview in a chat room with streamed questions, adaptive follow-ups and resume-after-reload, drag-and-drop or paste a resume, JD and extra documents, watch each file go Uploaded → Parsing → Ready, and view the extracted text and detected sections
- API:
  - `POST /sessions`, `GET /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`
  - `POST /sessions/{id}/analyze` (starts profile, JD and gap analysis), `GET` and `PATCH /sessions/{id}/analysis`
  - `POST /sessions/{id}/plan`, `GET /sessions/{id}/plan` (topic outline only; the questions stay hidden)
  - `WS /sessions/{id}/interview` (messages in: `start`, `answer`, `end`; out: `state`, `thinking`, `token`, `question`, `complete`, `error`), `GET /sessions/{id}/interview` (transcript), `POST /sessions/{id}/finish`
  - `POST /sessions/{id}/documents` (multipart: `kind` = resume | jd | other, and `file`), `GET` list and detail, `DELETE`
- Parsing: PDF (PyMuPDF with pdfplumber fallback), DOCX and TXT parsing, cleaning and section detection
- Parsing runs in the background. Each document moves through `uploaded`, `parsing`, then `ready` or `failed`.

Settings come from environment variables prefixed `AIA_`, for example `AIA_MAX_UPLOAD_MB`.

## Licence

MIT

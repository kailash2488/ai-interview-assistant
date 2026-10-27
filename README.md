# AI Interview Assistant

An open-source web app for interview practice. Create an account, upload your resume and a job description, and the app runs a mock interview written for you and that role, then gives you a scored feedback report with a study plan.

You choose where the AI runs, per account:

- **Local (free and private):** open-source models through [Ollama](https://ollama.com). Your resume never leaves your computer. Slow on a laptop without a GPU.
- **Google Gemini (cloud, fast):** bring your own API key. A free key works. Your resume and job description are sent to Google.

Everything else is open source and free: FastAPI, React, SQLite and Qdrant.

| Landing page | Dashboard |
|---|---|
| ![Landing page](docs/screenshots/01-landing-hero.png) | ![Dashboard](docs/screenshots/19-dashboard.png) |
| **Analysis review** | **Interview by voice** |
| ![Analysis review](docs/screenshots/06-analysis.png) | ![Voice interview](docs/screenshots/17-voice-transcript.png) |
| **Feedback report** | **Progress across attempts** |
| ![Report](docs/screenshots/10-report.png) | ![Progress](docs/screenshots/13-progress-compare.png) |

Watch a walkthrough from sign-up to report: [docs/demo.mp4](docs/demo.mp4) (recorded with an earlier version of the interface, before the dashboard and voice mode). More screenshots (sign-up, settings, mobile, practising weak spots) are in [docs/screenshots/](docs/screenshots/).

## What it does

1. **Sign up or log in.** Visitors see a landing page that explains the app. Each account has its own interviews, reports and model settings. Once signed in, the dashboard shows your suggested next step, latest and average score, practice streak, a score trend, the topics you should work on, how you score on each part of the rubric, milestones you have earned, and an interview tip.
2. **Create an interview:** target role, type (technical, behavioural or mixed), difficulty and number of topics.
3. **Upload documents:** resume (PDF, DOCX or TXT), job description (file or pasted text) and optional extras. Each file shows Uploaded, Parsing, then Ready, and you can read the extracted text.
4. **Analysis:** the model extracts your profile and the job's requirements. You review and correct them (add or remove skills) before anything else happens. A gap analysis shows matching skills, gaps and claims the interviewer will probe.
5. **Plan:** a topic outline (introduction, core skills, project deep dives, gap areas, behavioural, your questions). The questions stay hidden so the interview feels real.
6. **Live interview:** a chat with streamed questions and adaptive follow-ups. The interviewer never shows scores or hints. If you reload the page you pick up where you left off. Switch on **voice mode** to hear each question and answer by speaking (see [Voice mode](#voice-mode)).
7. **Feedback report (only when you ask for it):** every answer is scored 1 to 5 on accuracy, depth, relevance, structure and evidence, each with a quote from your answer. You get an overall score and verdict, scores by topic and dimension, strengths and improvement areas, a per-question breakdown with a stronger sample answer, communication notes and a two-week study plan. Download it as a PDF.
8. **Practise again:** start a new interview from the same documents without uploading or analysing anything twice, either the same interview again or one that asks your weakest topics first.
9. **Progress:** compare two attempts side by side to see what improved.
10. **Privacy controls:** delete one interview, all your data, or your whole account from the app.

## Quick start with Docker

You need Docker. Then:

```bash
git clone https://github.com/kailash2488/ai-interview-assistant.git
cd ai-interview-assistant
docker compose up --build
```

Open http://localhost:8080, create an account, then open **Settings** to pick a model:

- **Gemini (easiest):** choose Gemini, paste a key from [Google AI Studio](https://aistudio.google.com/apikey), save, and press Test connection.
- **Local model with Ollama on this computer:** install Ollama and run `ollama pull mistral:7b` and `ollama pull nomic-embed-text`. Docker containers cannot reach an Ollama that listens only on `127.0.0.1` (the default). Either make it listen on all interfaces (for example `OLLAMA_HOST=0.0.0.0`, which also exposes it to your network) or use the next option.
- **Local model with Ollama inside Docker:**
  ```bash
  OLLAMA_URL=http://ollama:11434 docker compose --profile local-llm up --build
  docker compose exec ollama ollama pull mistral:7b
  docker compose exec ollama ollama pull nomic-embed-text
  ```
  (This path is configured but has not been tested end to end.)

Change the port with `APP_PORT=9000 docker compose up`. Your data lives in Docker volumes; `docker compose down -v` removes it.

If you create `backend/.env` (see `backend/.env.example`), compose passes it to the backend, so a server-wide Gemini key and model apply to every account that has not set its own. The file is git-ignored; keep it that way.

**If the build is very slow or fails downloading packages** (some machines have slow container networking), build on the host's network and then start without rebuilding: `docker build --network=host -t ai_assistant-backend:latest ./backend && docker compose up -d`.

**Before you expose it to other people:** the first account is created by whoever gets there first, so create yours straight away, then close registration with `ALLOW_SIGNUP=false` (see [Accounts and security](#accounts-and-security)) and serve the app over HTTPS with `COOKIE_SECURE=true`.

## Run without Docker

Needs Python 3.10 or later and Node 20 or later.

```bash
# backend (terminal 1)
cd backend
python -m venv ../env && source ../env/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload          # API docs at http://localhost:8000/docs

# frontend (terminal 2)
cd frontend
npm install
npm run dev                            # http://localhost:5173, proxies /api to port 8000
```

`frontend/.npmrc` sets `legacy-peer-deps=true`, which works around a peer-dependency crash in npm 10.

If you used an earlier version without accounts, the first account you create adopts those interviews and the saved model settings.

## Accounts and security

- **Passwords** are hashed with scrypt (a unique salt per user). They are never stored or logged in plain text.
- **Sessions** use a random token in an `HttpOnly`, `SameSite=Lax` cookie. Only a hash of the token is stored in the database, so a leaked database does not hand out working sessions. Sessions last 30 days, end on log out, and a password change signs out every other browser.
- **Login attempts** are limited: after 5 wrong passwords for an email from one address, logins are refused for 15 minutes. Unknown emails and wrong passwords give the same answer and take the same time. The limit is kept in memory, so it resets when the server restarts and is per server process.
- **Every API route and the interview WebSocket require a signed-in account**, and every interview, document, report and setting belongs to one account. Another account's interview looks exactly like one that does not exist. The WebSocket also checks the browser's `Origin`.
- **API keys** are encrypted in the database with a server secret (`AIA_SECRET_KEY`, or a random key created in `backend/data/secret.key`). Back that file up with the database: without it, saved keys cannot be decrypted and users simply enter them again. Keys are never sent back to the browser.
- **There is no email service**, so there is no "forgot password" link and no email verification. The server owner can reset a password with `python backend/scripts/reset_password.py someone@example.com` (in Docker: `docker compose exec backend python -m scripts.reset_password someone@example.com`).
- **Set `AIA_ALLOW_SIGNUP=false`** once your accounts exist, and **`AIA_COOKIE_SECURE=true`** when serving over HTTPS.

## Voice mode

Answer by speaking instead of typing, and hear each question read aloud. Everything runs locally: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) turns your recording into text and [Piper](https://github.com/rhasspy/piper) speaks the questions, so your voice never leaves the server you run. It is optional and off by default.

```bash
cd backend
pip install -e ".[voice]"
python scripts/download_voice.py       # about 200 MB, once
```

With Docker: `INSTALL_VOICE=1 docker compose up --build`, then `docker compose exec backend python scripts/download_voice.py` once. This was built and tested end to end (speaking a question and transcribing an answer inside the container).

In the interview room turn on **Voice mode**. Press the microphone, speak, and it stops by itself when you go quiet (or press the square). The text appears in the answer box so you can fix mistakes before you send it. Your pace (words per minute) and long pauses are measured from the recording and shown in the report's communication section.

- If the server has no speech models, voice mode says so, and questions can still be read aloud by your browser's own voice. Typing always works.
- Browsers only allow microphone access on `localhost` or over HTTPS.
- The speech-to-text model is English only and sometimes mishears technical terms (it heard "asyncio" as "a sync I.O."). That is why you can edit the text before sending. `AIA_WHISPER_MODEL=small.en` is more accurate and slower.
- Filler words ("um", "uh") are not reported for spoken answers, because speech recognition usually leaves them out of the transcript.
- The first question and the first transcription load the models and take a few extra seconds.

## Choosing a model

| | Local (Ollama) | Gemini |
|---|---|---|
| Cost | Free | Free tier with rate limits, or paid |
| Privacy | Stays on your computer | Sent to Google; the free tier may be used to improve Google's products |
| Speed on a CPU-only laptop | Analysis about 2 minutes, each interview turn 10 to 60 seconds | Analysis about 5 seconds, each turn 2 to 4 seconds |
| Setup | Install Ollama, pull two models | Paste a key |

Local benchmark on 8 sample documents (see [docs/benchmarks/](docs/benchmarks/)): `mistral:7b` gave 100% valid JSON and 88% skill recall in about 43 s per document; `qwen2.5:7b` gave 100% and 91% in about 60 s. `mistral:7b` is the default.

Gemini models offered in Settings: `gemini-3.5-flash-lite` (recommended), `gemini-3.8-flash`, `gemini-3.6-flash` and `gemini-3.1-pro-preview`. During testing `gemini-3.8-flash` was often overloaded on the free tier, so Flash-Lite is the default. Check your own limits in AI Studio. Free-tier limits are per minute, so a long report may pause and retry.

Each account picks its own model and key on the Settings page. Check the server defaults from a terminal with `python backend/scripts/check_llm.py`.

## Configuration

Server settings come from environment variables prefixed `AIA_`, or a `backend/.env` file (see `backend/.env.example`). Model and key choices are made per account on the Settings page; the values below are only the defaults for accounts that have not chosen.

| Variable | Default | Meaning |
|---|---|---|
| `AIA_ALLOW_SIGNUP` | `true` | `false` closes registration |
| `AIA_COOKIE_SECURE` | `false` | `true` when served over HTTPS |
| `AIA_SECRET_KEY` | generated | Encrypts stored API keys |
| `AIA_LLM_PROVIDER` | `ollama` | Default provider: `ollama` or `gemini` |
| `AIA_GEMINI_API_KEY` | none | Optional shared Gemini key for accounts without their own |
| `AIA_GEMINI_MODEL` | `gemini-3.5-flash-lite` | Default Gemini model |
| `AIA_OLLAMA_URL` | `http://localhost:11434` | Where Ollama runs |
| `AIA_INTERVIEWER_MODEL`, `AIA_EVALUATOR_MODEL` | `mistral:7b` | Ollama chat models |
| `AIA_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `AIA_WHISPER_MODEL` | `base.en` | Speech-to-text model for voice mode |
| `AIA_PIPER_VOICE` | `en_US-lessac-medium` | Text-to-speech voice for voice mode |
| `AIA_MAX_UPLOAD_MB` | `10` | Upload size limit |
| `AIA_MAX_OTHER_DOCUMENTS` | `10` | Extra documents per interview |

## How it works

```
React (Vite)  --REST + WebSocket-->  FastAPI
                                       |- auth        accounts, sessions, per-user data and model settings
                                       |- ingestion   parse -> clean -> section -> embed
                                       |- analysis    profile, requirements, gap analysis (gap in plain code)
                                       |- interview   plan (plain code) + state machine + interviewer
                                       |- feedback    rubric evaluator, guards, report, PDF
                                       |- voice       optional local speech-to-text and text-to-speech
                                       |- dashboard   stats, trend, weak topics, milestones, practise again
                                       |- llm         Ollama or Gemini client, JSON-schema output, retry
                                       +- SQLite + embedded Qdrant
```

Design rules:

- **The code decides, the model writes.** The interview plan, follow-up limits, scores, verdict and gap analysis are plain code. The model only writes question wording, judges individual answers and writes the report text.
- **Structured outputs everywhere.** Model replies are validated against Pydantic schemas, retried once, and fall back safely (for example to a planned question).
- **Small models first.** Short prompts, one task per call, a worked example in each prompt. Prompts live in [backend/app/prompts/](backend/app/prompts/).
- **Honest scoring.** A score above 3 needs a quote that really appears in the answer. Very short answers cannot score high on depth or evidence. Strengths only come from topics that scored well. `python backend/scripts/calibrate.py` checks that the evaluator ranks hand-labelled strong, average and weak answers correctly (with `gemini-3.5-flash-lite`: strong 94 to 100, average 44 to 61, weak 7 to 26).
- **Uploaded text is data.** Resume, job description and answers are delimited in prompts and the model is told never to follow instructions inside them.

## Tests

```bash
cd backend && pytest                  # 290+ tests; add --cov=app for coverage (about 97%)
cd frontend && npm test               # 150 tests
```

The language model is replaced by a fake in tests, so they need no network or API key. A few voice tests use the real local speech models and are skipped automatically when those are not installed.

## Project layout

```
backend/app/api         routers (auth, sessions, documents, analysis, interview, report, history, settings, data)
backend/app/services    ingestion, analysis, interview, feedback, llm, vectorstore
backend/app/prompts     versioned prompt templates
backend/scripts         benchmark.py, calibrate.py, check_llm.py, reset_password.py, download_voice.py
frontend/src            pages, components, API client, auth state
data/samples            sample resumes, job descriptions, calibration answers
docs                    SOP.pdf (the original plan), benchmarks, screenshots, demo video
```

## Limitations

- Local models on a CPU-only laptop are slow. Use Gemini or a machine with a GPU for a smooth experience.
- Scores come from a rubric applied by a language model, so they are good for comparing your own attempts over time and for spotting weak areas. They are not a hiring decision.
- English only. Voice mode needs the optional speech models (see above). There is no email verification and no emailed password reset (see above for the owner's reset tool).
- Scanned PDFs are not supported (no OCR).
- Long jobs run as background tasks inside the API process. If you restart the backend during an analysis or report, start it again from the app. Run a single backend process, because login throttling and background jobs live in memory.

## Roadmap

Coding and system-design interview rounds, company-specific question banks from your own notes, and more languages. See [docs/SOP.pdf](docs/SOP.pdf).

## Licence

MIT

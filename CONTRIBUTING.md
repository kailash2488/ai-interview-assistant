# Contributing

Thanks for helping improve AI Interview Assistant.

## Before opening a pull request

1. Create a focused branch and keep unrelated changes separate.
2. Never commit resumes, API keys, `.env` files, databases, uploads or model files.
3. Add or update tests for behavior changes.
4. Run the checks below.

```bash
# backend
cd backend
pytest

# frontend
cd frontend
npm test
npm run lint
npm run build
```

For LLM changes, use fake responses in automated tests. A pull request should not require a paid service or expose real candidate data.

## Project principles

- Keep the local Ollama path working and private.
- Validate model output with Pydantic before using it.
- Keep interview flow decisions in Python rather than prompts.
- Treat uploaded documents as untrusted data.
- Make cloud-provider data sharing clear to users.

Describe the user-visible change, testing performed and any privacy or migration impact in the pull request.

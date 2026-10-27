# Security policy

## Reporting a vulnerability

Please do not publish exploitable security issues in a public issue. Report them privately through GitHub's **Security → Report a vulnerability** feature for this repository. Include reproduction steps, affected versions and potential impact.

## Sensitive data

This application processes resumes, job descriptions, interview answers and API credentials. Before sharing logs, screenshots or test fixtures, remove personal information and secrets.

- Keep `.env`, database, upload, encryption-key and voice-model files out of Git.
- Cloud providers receive the content needed for AI tasks when selected. Review their retention policies.
- Use HTTPS, secure cookies and closed registration before exposing the app outside a trusted machine.
- Back up `secret.key` with the database. Without it, saved provider credentials cannot be decrypted.

Supported security fixes target the current `main` branch.

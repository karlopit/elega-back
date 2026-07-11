# AGENTS.md — Backend (FastAPI)

This file gives AI coding agents (Claude Code, Codex, Cursor, etc.) the context and rules needed to work on this repository. Read this before making changes.

## Project Overview

FastAPI backend for an online clothing store. Provides a REST API consumed by a separate Next.js frontend (polyrepo — frontend lives in a different repository). Deployed on Render (free tier). Database is Postgres via Supabase.

## Tech Stack

- Python 3.11+
- FastAPI
- Pydantic (request/response validation)
- Supabase (Postgres database, and optionally Auth)
- Uvicorn (ASGI server)
- Deployed on Render

## Project Structure

```
api/
├── main.py              # FastAPI app entrypoint
├── routers/              # One file per resource (products, cart, orders, auth)
├── models/                # Pydantic schemas
├── db/                    # Database connection/session handling
├── core/                   # Config, settings, env var loading
└── requirements.txt
```

## Commands

- Install dependencies: `pip install -r requirements.txt`
- Run locally: `uvicorn main:app --reload`
- Run in production (Render start command): `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Run tests: `pytest`

## Code Style Rules

- **No emojis** anywhere in code, comments, commit messages, log output, or API responses.
- Code must be clean but still understandable — prioritize readability over cleverness. Prefer clear variable/function names over compressed one-liners.
- Follow PEP 8. Use type hints on all function signatures.
- Every endpoint must have a docstring explaining what it does, its expected inputs, and its outputs.
- Keep functions short and single-purpose. If a function is doing more than one clear thing, split it.
- No commented-out dead code left in commits.
- Consistent naming: snake_case for variables/functions, PascalCase for Pydantic models/classes.

## Security Requirements (mandatory, non-negotiable)

- **Input validation**: All request bodies, query params, and path params must be validated via Pydantic models. Never trust raw input.
- **SQL injection protection**: Never build raw SQL with string concatenation or f-strings. Use parameterized queries or the Supabase/ORM client methods exclusively.
- **Rate limiting**: All public-facing endpoints must be rate-limited (e.g. via `slowapi` or equivalent middleware). Auth endpoints (login, register, password reset) require stricter limits than general read endpoints.
- **CORS**: Restrict `allow_origins` to the known frontend domain(s) explicitly. Never use `allow_origins=["*"]` in production.
- **Secrets management**: No API keys, database URLs, or credentials committed to the repo. All secrets loaded from environment variables via `core/config.py`. `.env` must be in `.gitignore`.
- **Auth**: Passwords never stored or logged in plaintext. Use hashed passwords (bcrypt/argon2) if not fully delegating to Supabase Auth. JWT tokens must have expiration set.
- **HTTPS only**: Assume all traffic is HTTPS in production; do not disable Render's forced HTTPS.
- **Error handling**: Never leak stack traces, internal file paths, or database errors to API responses. Return generic error messages to the client; log details server-side only.
- **Dependency hygiene**: Keep `requirements.txt` pinned to specific versions. Flag outdated or vulnerable packages when noticed.
- **Least privilege**: Database credentials used by the API should have only the permissions the API actually needs, not full admin rights.

## General Development Practices

- Write a test for every new endpoint before considering it done.
- Use meaningful HTTP status codes (200, 201, 400, 401, 403, 404, 422, 429, 500) — don't default everything to 200 or 500.
- Log errors and important events server-side, but never log sensitive data (passwords, tokens, full card numbers).
- Every new endpoint must be documented — FastAPI's auto-generated `/docs` (Swagger UI) should stay accurate; don't suppress or break it.
- Commit messages should be clear and describe *why*, not just *what* (e.g. "Add rate limiting to /login to prevent brute force" not "update auth.py").
- Before marking a feature complete, verify it against the security checklist above, not just that it "works."

## What NOT to Do

- Do not add emojis to any output, code, or messages.
- Do not hardcode secrets, URLs, or credentials.
- Do not disable CORS, rate limiting, or validation "temporarily" and leave it disabled.
- Do not introduce new dependencies without a clear reason noted in the commit message.
- Do not silently swallow exceptions — handle them explicitly or let them propagate with proper logging.

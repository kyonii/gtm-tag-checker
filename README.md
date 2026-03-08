# GTM Tag Checker

A web app that audits GTM container health via Google OAuth — checks for firing issues, unused tags, and duplicate tracking.

> Google OAuthでサインインしてGTMコンテナの健全性を監査するWebアプリ。

## Checks

| ID | Description | Severity |
|----|-------------|----------|
| FIRE-001 | Tags without firing triggers | Error |
| FIRE-002 | Paused tags | Warning |
| FIRE-003 | GA4 tags missing Measurement ID | Error |
| UNUSED-001 | Unused triggers | Warning |
| UNUSED-002 | Duplicate GA4 Configuration tags | Error |
| UNUSED-003 | Tags with suspicious names (test/temp/old...) | Warning |
| DUP-001 | Tags with duplicate type + trigger combinations | Error |
| DUP-002 | Both Universal Analytics and GA4 tags active | Warning |

## Health Score

Starts at 100. Each failed check deducts points: **-10** per Error, **-3** per Warning.

## Setup

```bash
poetry install
cp .env.example .env
# Fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET_KEY
poetry run uvicorn app.main:app --reload
```

In Google Cloud Console, create an OAuth client and add `http://localhost:8000/auth/callback` as a redirect URI.

## Tests

```bash
poetry run pytest tests/ -v
```

All checks are implemented as pure functions with no external dependencies — no network calls needed to run tests.

## Stack

- **FastAPI** + Jinja2 templates
- **Google OAuth2** with signed-cookie sessions (no DB required)
- **httpx** async GTM API client (DI-friendly for testing)
- **Pydantic v2** models
- **Poetry** for dependency management

---

> ## セットアップ（日本語）
>
> ```bash
> poetry install
> cp .env.example .env
> # .envにGOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET_KEYを記入
> poetry run uvicorn app.main:app --reload
> ```
>
> Google Cloud ConsoleでOAuthクライアントを作成し、リダイレクトURIに `http://localhost:8000/auth/callback` を追加してください。

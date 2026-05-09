# User API

FastAPI service that owns user registration, login, and access tokens.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 4002
```

Use `POST /auth/register` or `POST /auth/login` to get an access token. Send
that token to `todo-api` as `Authorization: Bearer <token>`.

`POST /auth/logout` revokes the current token. `todo-api` validates tokens by
calling `POST /auth/introspect` with the internal `X-Service-Token` header.

# Todo API

FastAPI service that owns todo list behavior and persistence.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 4001
```

By default the API uses `sqlite:///./todo-api.db`. In Docker Compose it uses the
`DATABASE_URL` provided by the root `docker-compose.yml`.

## Endpoints

- `GET /health`
- `GET /todos`
- `POST /todos`
- `PATCH /todos/{todo_id}`
- `DELETE /todos/{todo_id}`


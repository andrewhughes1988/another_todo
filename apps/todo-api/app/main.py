from contextlib import asynccontextmanager
import os

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .auth import TokenUser, get_current_user
from .database import Base, engine, get_db
from .models import Todo
from .schemas import TodoCreate, TodoRead, TodoUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: Replace startup table creation with Alembic migrations during the database phase.
    Base.metadata.create_all(bind=engine)
    yield


MAX_WRITE_BODY_BYTES = 4096
APP_ENV = os.getenv("APP_ENV", "development")
LOCAL_DEV_ORIGIN_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|host\.docker\.internal|\[::1\]|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$"
)
ALLOWED_CORS_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
ALLOWED_CORS_HEADERS = ["Authorization", "Content-Type"]

if APP_ENV == "production" and not os.getenv("CORS_ALLOW_ORIGINS"):
    raise RuntimeError("CORS_ALLOW_ORIGINS must be set in production")


def get_api_docs_url(path: str) -> str | None:
    return None if APP_ENV == "production" else path


app = FastAPI(
    title="Todo API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=get_api_docs_url("/docs"),
    redoc_url=get_api_docs_url("/redoc"),
    openapi_url=get_api_docs_url("/openapi.json"),
)


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOW_ORIGINS")

    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def get_cors_origin_regex() -> str | None:
    configured = os.getenv("CORS_ALLOW_ORIGIN_REGEX")

    if configured:
        return configured

    return LOCAL_DEV_ORIGIN_REGEX if APP_ENV != "production" else None


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=get_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=ALLOWED_CORS_METHODS,
    allow_headers=ALLOWED_CORS_HEADERS,
)


@app.middleware("http")
async def limit_write_request_size(request: Request, call_next):
    if request.method in {"POST", "PATCH"}:
        content_length = request.headers.get("content-length")

        try:
            body_size = int(content_length) if content_length else 0
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid Content-Length header"},
            )

        if body_size > MAX_WRITE_BODY_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={"detail": "Request body is too large"},
            )

    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/todos", response_model=list[TodoRead])
def list_todos(
    db: Session = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
) -> list[Todo]:
    return db.query(Todo).filter(Todo.owner_id == current_user.id).order_by(Todo.created_at.desc()).all()


@app.post("/todos", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
def create_todo(
    payload: TodoCreate,
    db: Session = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
) -> Todo:
    todo = Todo(title=payload.title, owner_id=current_user.id)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


@app.patch("/todos/{todo_id}", response_model=TodoRead)
def update_todo(
    todo_id: int,
    payload: TodoUpdate,
    db: Session = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
) -> Todo:
    todo = db.query(Todo).filter(Todo.id == todo_id, Todo.owner_id == current_user.id).one_or_none()

    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(todo, field, value)

    db.commit()
    db.refresh(todo)
    return todo


@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(
    todo_id: int,
    db: Session = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
) -> Response:
    todo = db.query(Todo).filter(Todo.id == todo_id, Todo.owner_id == current_user.id).one_or_none()

    if todo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")

    db.delete(todo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

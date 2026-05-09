import hmac
import os
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import create_access_token, get_token_identity, hash_password, verify_password
from .database import Base, engine, get_db
from .models import User
from .schemas import AuthToken, TokenIntrospectionRequest, TokenIntrospectionResponse, UserLogin, UserRegister


DEFAULT_SERVICE_AUTH_TOKEN = "local-dev-service-token-32-bytes-minimum"
SERVICE_AUTH_TOKEN = os.getenv("SERVICE_AUTH_TOKEN", DEFAULT_SERVICE_AUTH_TOKEN)
APP_ENV = os.getenv("APP_ENV", "development")
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 10
# TODO: Move rate-limit buckets and token revocation state to Redis before running multiple user-api replicas.
rate_limit_attempts: dict[str, deque[float]] = defaultdict(deque)
revoked_token_ids: set[str] = set()

if APP_ENV == "production" and SERVICE_AUTH_TOKEN == DEFAULT_SERVICE_AUTH_TOKEN:
    raise RuntimeError("SERVICE_AUTH_TOKEN must be set to a production secret")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: Replace startup table creation with Alembic migrations during the database phase.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="User API", version="0.1.0", lifespan=lifespan)
MAX_WRITE_BODY_BYTES = 4096

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_write_request_size(request: Request, call_next):
    if request.method == "POST":
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


@app.post("/auth/register", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
def register(request: Request, payload: UserRegister, db: Session = Depends(get_db)) -> AuthToken:
    enforce_rate_limit(f"register:{request.client.host if request.client else 'unknown'}")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from error

    db.refresh(user)
    return AuthToken(access_token=create_access_token(user), user=user)


@app.post("/auth/login", response_model=AuthToken)
def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)) -> AuthToken:
    enforce_rate_limit(f"login:{request.client.host if request.client else 'unknown'}:{payload.email}")
    user = db.query(User).filter(User.email == payload.email).one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return AuthToken(access_token=create_access_token(user), user=user)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(authorization: str | None = Header(default=None)) -> Response:
    token = get_bearer_token(authorization)
    _, _, token_id = get_token_identity(token)
    revoked_token_ids.add(token_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/auth/introspect", response_model=TokenIntrospectionResponse)
def introspect(
    payload: TokenIntrospectionRequest,
    x_service_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> TokenIntrospectionResponse:
    if not hmac.compare_digest(x_service_token or "", SERVICE_AUTH_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")

    user_id, _, token_id = get_token_identity(payload.token)

    if token_id in revoked_token_ids:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return TokenIntrospectionResponse(active=True, user=user)


def enforce_rate_limit(key: str) -> None:
    now = monotonic()
    attempts = rate_limit_attempts[key]

    while attempts and now - attempts[0] > RATE_LIMIT_WINDOW_SECONDS:
        attempts.popleft()

    if len(attempts) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")

    attempts.append(now)


def get_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token

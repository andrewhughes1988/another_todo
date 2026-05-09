import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import create_access_token, decode_access_token, get_token_identity, hash_password, verify_password
from .database import Base, engine, get_db
from .models import RateLimitAttempt, RevokedToken, User
from .schemas import AuthToken, TokenIntrospectionRequest, TokenIntrospectionResponse, UserLogin, UserRegister


DEFAULT_SERVICE_AUTH_TOKEN = "local-dev-service-token-32-bytes-minimum"
SERVICE_AUTH_TOKEN = os.getenv("SERVICE_AUTH_TOKEN", DEFAULT_SERVICE_AUTH_TOKEN)
APP_ENV = os.getenv("APP_ENV", "development")
LOCAL_DEV_ORIGIN_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|host\.docker\.internal|\[::1\]|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$"
)
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 10

if APP_ENV == "production" and SERVICE_AUTH_TOKEN == DEFAULT_SERVICE_AUTH_TOKEN:
    raise RuntimeError("SERVICE_AUTH_TOKEN must be set to a production secret")


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: Replace startup table creation with Alembic migrations during the database phase.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="User API", version="0.1.0", lifespan=lifespan)
MAX_WRITE_BODY_BYTES = 4096

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=get_cors_origin_regex(),
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
    enforce_rate_limit(db, f"register:{request.client.host if request.client else 'unknown'}")
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
    enforce_rate_limit(db, f"login:{request.client.host if request.client else 'unknown'}:{payload.email}")
    user = db.query(User).filter(User.email == payload.email).one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    return AuthToken(access_token=create_access_token(user), user=user)


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Response:
    token = get_bearer_token(authorization)
    claims = decode_access_token(token)
    _, _, token_id = get_token_identity(token)
    expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=timezone.utc)

    prune_expired_revoked_tokens(db)

    if db.query(RevokedToken).filter(RevokedToken.token_id == token_id).one_or_none() is None:
        db.add(RevokedToken(token_id=token_id, expires_at=expires_at))
        db.commit()

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

    prune_expired_revoked_tokens(db)

    if db.query(RevokedToken).filter(RevokedToken.token_id == token_id).one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return TokenIntrospectionResponse(active=True, user=user)


def enforce_rate_limit(db: Session, key: str) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)

    db.query(RateLimitAttempt).filter(RateLimitAttempt.created_at < cutoff).delete(synchronize_session=False)
    attempt_count = db.query(RateLimitAttempt).filter(RateLimitAttempt.bucket_key == key).count()

    if attempt_count >= RATE_LIMIT_MAX_ATTEMPTS:
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts")

    db.add(RateLimitAttempt(bucket_key=key, created_at=now))
    db.commit()


def prune_expired_revoked_tokens(db: Session) -> None:
    db.query(RevokedToken).filter(RevokedToken.expires_at <= datetime.now(timezone.utc)).delete(
        synchronize_session=False
    )
    db.commit()


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

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from .models import User


DEFAULT_SECRET_KEY = "local-dev-secret-change-me-32-bytes-min"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
APP_ENV = os.getenv("APP_ENV", "development")
TOKEN_ISSUER = os.getenv("TOKEN_ISSUER", "user-api")
TOKEN_AUDIENCE = os.getenv("TOKEN_AUDIENCE", "todo-api")
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "60"))
PASSWORD_ITERATIONS = 600_000
ALGORITHM = "HS256"

if APP_ENV == "production" and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set to a production secret")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${password_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected_hash = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    ).hex()
    return hmac.compare_digest(actual_hash, expected_hash)


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    issued_at = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "iat": issued_at,
            "exp": expires_at,
            "jti": secrets.token_urlsafe(32),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, object]:
    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={"require": ["sub", "email", "iss", "aud", "exp", "jti"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


def get_token_identity(token: str) -> tuple[int, str, str]:
    payload = decode_access_token(token)
    subject = payload.get("sub")
    email = payload.get("email")
    token_id = payload.get("jti")

    if not isinstance(subject, str) or not subject.isdigit():
        raise_invalid_token()

    if not isinstance(email, str) or not email:
        raise_invalid_token()

    if not isinstance(token_id, str) or not token_id:
        raise_invalid_token()

    return int(subject), email, token_id


def raise_invalid_token() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )

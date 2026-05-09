import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
TOKEN_ISSUER = os.getenv("TOKEN_ISSUER", "user-api")
TOKEN_AUDIENCE = os.getenv("TOKEN_AUDIENCE", "todo-api")
security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class TokenUser:
    id: int
    email: str


def decode_token(token: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError:
        raise_invalid_token()

    try:
        header = json.loads(base64url_decode(header_segment))
    except (ValueError, json.JSONDecodeError):
        raise_invalid_token()

    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise_invalid_token()

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()

    if not hmac.compare_digest(base64url_encode(expected_signature), signature_segment):
        raise_invalid_token()

    try:
        payload = json.loads(base64url_decode(payload_segment))
    except (ValueError, json.JSONDecodeError):
        raise_invalid_token()

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or datetime.now(timezone.utc).timestamp() >= expires_at:
        raise_invalid_token("Token has expired")

    issuer = payload.get("iss")
    if issuer != TOKEN_ISSUER:
        raise_invalid_token()

    audience = payload.get("aud")
    if audience != TOKEN_AUDIENCE:
        raise_invalid_token()

    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    subject = payload.get("sub")

    if not isinstance(subject, str) or not subject.isdigit():
        raise_invalid_token()

    email = payload.get("email")
    if not isinstance(email, str) or not email:
        raise_invalid_token()

    return TokenUser(id=int(subject), email=email)


def base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def raise_invalid_token(detail: str = "Invalid token") -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )

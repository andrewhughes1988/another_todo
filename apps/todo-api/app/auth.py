import os
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


USER_API_URL = os.getenv("USER_API_URL", "http://localhost:4002").rstrip("/")
SERVICE_AUTH_TOKEN = os.getenv("SERVICE_AUTH_TOKEN", "local-dev-service-token-32-bytes-minimum")
APP_ENV = os.getenv("APP_ENV", "development")
INTROSPECTION_TIMEOUT_SECONDS = 2.0
security = HTTPBearer(auto_error=False)

if APP_ENV == "production" and SERVICE_AUTH_TOKEN == "local-dev-service-token-32-bytes-minimum":
    raise RuntimeError("SERVICE_AUTH_TOKEN must be set to a production secret")


@dataclass(frozen=True)
class TokenUser:
    id: int
    email: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = httpx.post(
            f"{USER_API_URL}/auth/introspect",
            json={"token": credentials.credentials},
            headers={"X-Service-Token": SERVICE_AUTH_TOKEN},
            timeout=INTROSPECTION_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User API is unavailable",
        ) from error

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User API introspection failed",
        )

    payload = response.json()
    user = payload.get("user")

    if not payload.get("active") or not isinstance(user, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = user.get("id")
    email = user.get("email")

    if not isinstance(user_id, int) or not isinstance(email, str) or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenUser(id=user_id, email=email)

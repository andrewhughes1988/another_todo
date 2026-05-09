import base64
import hashlib
import hmac
import json
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import SECRET_KEY, TOKEN_AUDIENCE, TOKEN_ISSUER
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def auth_headers(user_id: int = 1, email: str = "ada@example.com") -> dict[str, str]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = sign_test_token(
        {
            "sub": str(user_id),
            "email": email,
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "exp": int(expires_at.timestamp()),
        }
    )
    return {"Authorization": f"Bearer {token}"}


def sign_test_token(payload: dict[str, object]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    return sign_test_token_with_header(header, payload)


def sign_test_token_with_header(header: dict[str, object], payload: dict[str, object]) -> str:
    segments = [
        base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("utf-8")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(base64url_encode(signature))
    return ".".join(segments)


def base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rejects_unauthenticated_todo_access(client: TestClient) -> None:
    response = client.get("/todos")

    assert response.status_code == 401


def test_rejects_token_from_wrong_issuer(client: TestClient) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = sign_test_token(
        {
            "sub": "1",
            "email": "ada@example.com",
            "iss": "other-service",
            "aud": TOKEN_AUDIENCE,
            "exp": int(expires_at.timestamp()),
        }
    )

    response = client.get("/todos", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_rejects_token_from_wrong_audience(client: TestClient) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
    token = sign_test_token(
        {
            "sub": "1",
            "email": "ada@example.com",
            "iss": TOKEN_ISSUER,
            "aud": "other-api",
            "exp": int(expires_at.timestamp()),
        }
    )

    response = client.get("/todos", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_rejects_tampered_token_payload(client: TestClient) -> None:
    token = auth_headers(user_id=1)["Authorization"].replace("Bearer ", "")
    header_segment, payload_segment, signature_segment = token.split(".")
    tampered_payload = {
        "sub": "2",
        "email": "grace@example.com",
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=60)).timestamp()),
    }
    tampered_token = ".".join(
        [
            header_segment,
            base64url_encode(json.dumps(tampered_payload, separators=(",", ":")).encode("utf-8")),
            signature_segment,
        ]
    )

    response = client.get("/todos", headers={"Authorization": f"Bearer {tampered_token}"})

    assert response.status_code == 401


def test_rejects_expired_token(client: TestClient) -> None:
    token = sign_test_token(
        {
            "sub": "1",
            "email": "ada@example.com",
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()),
        }
    )

    response = client.get("/todos", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_rejects_token_with_unexpected_algorithm(client: TestClient) -> None:
    token = sign_test_token_with_header(
        {"alg": "none", "typ": "JWT"},
        {
            "sub": "1",
            "email": "ada@example.com",
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=60)).timestamp()),
        },
    )

    response = client.get("/todos", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_create_and_list_todos(client: TestClient) -> None:
    headers = auth_headers()
    create_response = client.post("/todos", json={"title": "  Ship the API  "}, headers=headers)

    assert create_response.status_code == 201
    todo = create_response.json()
    assert todo["title"] == "Ship the API"
    assert todo["completed"] is False

    list_response = client.get("/todos", headers=headers)

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == todo["id"]


def test_update_todo(client: TestClient) -> None:
    headers = auth_headers()
    todo = client.post("/todos", json={"title": "Write tests"}, headers=headers).json()

    response = client.patch(
        f"/todos/{todo['id']}",
        json={"title": "Write focused tests", "completed": True},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Write focused tests"
    assert response.json()["completed"] is True


def test_delete_todo(client: TestClient) -> None:
    headers = auth_headers()
    todo = client.post("/todos", json={"title": "Delete me"}, headers=headers).json()

    delete_response = client.delete(f"/todos/{todo['id']}", headers=headers)
    list_response = client.get("/todos", headers=headers)

    assert delete_response.status_code == 204
    assert list_response.json() == []


def test_rejects_blank_title(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "   "}, headers=auth_headers())

    assert response.status_code == 422


def test_rejects_symbol_only_title(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "!!! --- ..."}, headers=auth_headers())

    assert response.status_code == 422


def test_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "Valid task", "owner_id": 1}, headers=auth_headers())

    assert response.status_code == 422


def test_rejects_empty_update(client: TestClient) -> None:
    headers = auth_headers()
    todo = client.post("/todos", json={"title": "Update me"}, headers=headers).json()

    response = client.patch(f"/todos/{todo['id']}", json={}, headers=headers)

    assert response.status_code == 422


def test_rejects_coerced_completed_value(client: TestClient) -> None:
    headers = auth_headers()
    todo = client.post("/todos", json={"title": "No coercion"}, headers=headers).json()

    response = client.patch(f"/todos/{todo['id']}", json={"completed": "true"}, headers=headers)

    assert response.status_code == 422


def test_rejects_large_write_body(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "x" * 5000})

    assert response.status_code == 413


def test_users_cannot_see_or_modify_each_others_todos(client: TestClient) -> None:
    first_user_headers = auth_headers(user_id=1, email="ada@example.com")
    second_user_headers = auth_headers(user_id=2, email="grace@example.com")
    todo = client.post("/todos", json={"title": "Private task"}, headers=first_user_headers).json()

    list_response = client.get("/todos", headers=second_user_headers)
    update_response = client.patch(f"/todos/{todo['id']}", json={"completed": True}, headers=second_user_headers)
    delete_response = client.delete(f"/todos/{todo['id']}", headers=second_user_headers)

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert update_response.status_code == 404
    assert delete_response.status_code == 404

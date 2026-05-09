from collections.abc import Generator
import base64
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import SERVICE_AUTH_TOKEN, app, rate_limit_attempts, revoked_token_ids


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
    rate_limit_attempts.clear()
    revoked_token_ids.clear()
    Base.metadata.drop_all(bind=engine)


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_and_login(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "  ADA@example.com  ", "password": "Password1"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "ada@example.com", "password": "Password1"},
    )

    assert register_response.status_code == 201
    assert register_response.json()["token_type"] == "bearer"
    assert register_response.json()["user"]["email"] == "ada@example.com"
    assert login_response.status_code == 200
    assert login_response.json()["access_token"]


def test_register_token_contains_expected_trust_claims(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "ada@example.com", "password": "Password1"},
    )

    token = response.json()["access_token"]
    _, payload_segment, _ = token.split(".")
    payload = json.loads(base64url_decode(payload_segment))

    assert payload["sub"] == str(response.json()["user"]["id"])
    assert payload["email"] == "ada@example.com"
    assert payload["iss"] == "user-api"
    assert payload["aud"] == "todo-api"
    assert isinstance(payload["exp"], int)
    assert isinstance(payload["jti"], str)


def test_introspects_valid_token(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "ada@example.com", "password": "Password1"},
    )
    token = register_response.json()["access_token"]

    response = client.post(
        "/auth/introspect",
        json={"token": token},
        headers={"X-Service-Token": SERVICE_AUTH_TOKEN},
    )

    assert response.status_code == 200
    assert response.json()["active"] is True
    assert response.json()["user"]["email"] == "ada@example.com"


def test_introspection_requires_service_token(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "ada@example.com", "password": "Password1"},
    )

    response = client.post("/auth/introspect", json={"token": register_response.json()["access_token"]})

    assert response.status_code == 401


def test_introspection_rejects_tampered_token(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "ada@example.com", "password": "Password1"},
    )
    header_segment, payload_segment, signature_segment = register_response.json()["access_token"].split(".")
    payload = json.loads(base64url_decode(payload_segment))
    payload["sub"] = "999"
    tampered_token = ".".join(
        [
            header_segment,
            base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
            signature_segment,
        ]
    )

    response = client.post(
        "/auth/introspect",
        json={"token": tampered_token},
        headers={"X-Service-Token": SERVICE_AUTH_TOKEN},
    )

    assert response.status_code == 401


def test_logout_revokes_token(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={"email": "ada@example.com", "password": "Password1"},
    )
    token = register_response.json()["access_token"]

    logout_response = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    introspect_response = client.post(
        "/auth/introspect",
        json={"token": token},
        headers={"X-Service-Token": SERVICE_AUTH_TOKEN},
    )

    assert logout_response.status_code == 204
    assert introspect_response.status_code == 401


def test_rejects_duplicate_registration(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "ada@example.com", "password": "Password1"})

    response = client.post("/auth/register", json={"email": "ada@example.com", "password": "Password1"})

    assert response.status_code == 409


def test_rejects_weak_registration_password(client: TestClient) -> None:
    response = client.post("/auth/register", json={"email": "ada@example.com", "password": "password"})

    assert response.status_code == 422


def test_rejects_invalid_login(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "ada@example.com", "password": "Password1"})

    response = client.post("/auth/login", json={"email": "ada@example.com", "password": "WrongPassword1"})

    assert response.status_code == 401


def test_rate_limits_login_attempts(client: TestClient) -> None:
    client.post("/auth/register", json={"email": "ada@example.com", "password": "Password1"})

    for _ in range(10):
        response = client.post("/auth/login", json={"email": "ada@example.com", "password": "WrongPassword1"})
        assert response.status_code == 401

    response = client.post("/auth/login", json={"email": "ada@example.com", "password": "WrongPassword1"})

    assert response.status_code == 429


def test_rate_limits_registration_attempts(client: TestClient) -> None:
    for index in range(10):
        response = client.post(
            "/auth/register",
            json={"email": f"ada{index}@example.com", "password": "Password1"},
        )
        assert response.status_code == 201

    response = client.post("/auth/register", json={"email": "ada10@example.com", "password": "Password1"})

    assert response.status_code == 429


def test_rejects_oversized_auth_request(client: TestClient) -> None:
    response = client.post("/auth/register", json={"email": "ada@example.com", "password": "x" * 5000})

    assert response.status_code == 413


def base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

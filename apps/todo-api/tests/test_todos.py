from collections.abc import Generator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import TokenUser, get_current_user
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


def use_user(user_id: int = 1, email: str = "ada@example.com") -> dict[str, str]:
    app.dependency_overrides[get_current_user] = lambda: TokenUser(id=user_id, email=email)
    return {"Authorization": "Bearer test-token"}


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_allows_local_frontend_todo_preflight(client: TestClient) -> None:
    response = client.options(
        "/todos",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_rejects_unauthenticated_todo_access(client: TestClient) -> None:
    response = client.get("/todos")

    assert response.status_code == 401


def test_rejects_token_from_wrong_issuer(client: TestClient) -> None:
    def reject_user() -> TokenUser:
        raise HTTPException(status_code=401, detail="Invalid token")

    app.dependency_overrides[get_current_user] = reject_user
    response = client.get("/todos", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_create_and_list_todos(client: TestClient) -> None:
    headers = use_user()
    create_response = client.post("/todos", json={"title": "  Ship the API  "}, headers=headers)

    assert create_response.status_code == 201
    todo = create_response.json()
    assert todo["title"] == "Ship the API"
    assert todo["completed"] is False

    list_response = client.get("/todos", headers=headers)

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == todo["id"]


def test_update_todo(client: TestClient) -> None:
    headers = use_user()
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
    headers = use_user()
    todo = client.post("/todos", json={"title": "Delete me"}, headers=headers).json()

    delete_response = client.delete(f"/todos/{todo['id']}", headers=headers)
    list_response = client.get("/todos", headers=headers)

    assert delete_response.status_code == 204
    assert list_response.json() == []


def test_rejects_blank_title(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "   "}, headers=use_user())

    assert response.status_code == 422


def test_rejects_symbol_only_title(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "!!! --- ..."}, headers=use_user())

    assert response.status_code == 422


def test_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "Valid task", "owner_id": 1}, headers=use_user())

    assert response.status_code == 422


def test_rejects_empty_update(client: TestClient) -> None:
    headers = use_user()
    todo = client.post("/todos", json={"title": "Update me"}, headers=headers).json()

    response = client.patch(f"/todos/{todo['id']}", json={}, headers=headers)

    assert response.status_code == 422


def test_rejects_coerced_completed_value(client: TestClient) -> None:
    headers = use_user()
    todo = client.post("/todos", json={"title": "No coercion"}, headers=headers).json()

    response = client.patch(f"/todos/{todo['id']}", json={"completed": "true"}, headers=headers)

    assert response.status_code == 422


def test_rejects_large_write_body(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "x" * 5000})

    assert response.status_code == 413


def test_users_cannot_see_or_modify_each_others_todos(client: TestClient) -> None:
    first_user_headers = use_user(user_id=1, email="ada@example.com")
    todo = client.post("/todos", json={"title": "Private task"}, headers=first_user_headers).json()

    second_user_headers = use_user(user_id=2, email="grace@example.com")
    list_response = client.get("/todos", headers=second_user_headers)
    update_response = client.patch(f"/todos/{todo['id']}", json={"completed": True}, headers=second_user_headers)
    delete_response = client.delete(f"/todos/{todo['id']}", headers=second_user_headers)

    assert list_response.status_code == 200
    assert list_response.json() == []
    assert update_response.status_code == 404
    assert delete_response.status_code == 404

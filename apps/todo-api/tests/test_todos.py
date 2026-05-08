from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_list_todos(client: TestClient) -> None:
    create_response = client.post("/todos", json={"title": "  Ship the API  "})

    assert create_response.status_code == 201
    todo = create_response.json()
    assert todo["title"] == "Ship the API"
    assert todo["completed"] is False

    list_response = client.get("/todos")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == todo["id"]


def test_update_todo(client: TestClient) -> None:
    todo = client.post("/todos", json={"title": "Write tests"}).json()

    response = client.patch(
        f"/todos/{todo['id']}",
        json={"title": "Write focused tests", "completed": True},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Write focused tests"
    assert response.json()["completed"] is True


def test_delete_todo(client: TestClient) -> None:
    todo = client.post("/todos", json={"title": "Delete me"}).json()

    delete_response = client.delete(f"/todos/{todo['id']}")
    list_response = client.get("/todos")

    assert delete_response.status_code == 204
    assert list_response.json() == []


def test_rejects_blank_title(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "   "})

    assert response.status_code == 422


def test_rejects_symbol_only_title(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "!!! --- ..."})

    assert response.status_code == 422


def test_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "Valid task", "owner_id": 1})

    assert response.status_code == 422


def test_rejects_empty_update(client: TestClient) -> None:
    todo = client.post("/todos", json={"title": "Update me"}).json()

    response = client.patch(f"/todos/{todo['id']}", json={})

    assert response.status_code == 422


def test_rejects_coerced_completed_value(client: TestClient) -> None:
    todo = client.post("/todos", json={"title": "No coercion"}).json()

    response = client.patch(f"/todos/{todo['id']}", json={"completed": "true"})

    assert response.status_code == 422


def test_rejects_large_write_body(client: TestClient) -> None:
    response = client.post("/todos", json={"title": "x" * 5000})

    assert response.status_code == 413

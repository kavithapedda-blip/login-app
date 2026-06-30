"""Smoke tests for the login service.

Run from the backend/ directory: ``pytest -v``
Uses FastAPI's TestClient (requires httpx, installed by the CI workflow).
"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "practice-login-app"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_login_success_returns_token():
    # 'admin' / 'secret' is the seeded default user.
    r = client.post("/login", json={"username": "admin", "password": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]  # non-empty JWT


def test_login_wrong_password_is_401():
    r = client.post("/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user_is_401():
    r = client.post("/login", json={"username": "ghost", "password": "secret"})
    assert r.status_code == 401


def test_register_then_login():
    creds = {"username": "alice", "password": "p@ssw0rd"}
    r = client.post("/register", json=creds)
    assert r.status_code == 201
    assert r.json()["username"] == "alice"

    # the newly registered user can log in
    r = client.post("/login", json=creds)
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_register_duplicate_is_409():
    # 'admin' already exists from app startup
    r = client.post("/register", json={"username": "admin", "password": "whatever"})
    assert r.status_code == 409

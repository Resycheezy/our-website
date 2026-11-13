"""
Gemeinsame Test-Hilfen (pytest "Fixtures").
Jeder Test bekommt eine eigene, leere SQLite-Datenbank in einem Temp-Ordner.
"""

import sys
from pathlib import Path

import pytest

# Damit "import app" und "import config" aus dem backend-Ordner funktionieren
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import limiter  # noqa: E402


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "SESSION_COOKIE_SECURE": False,  # Test-Client spricht http://, nicht https://
        "RATELIMIT_STORAGE_URI": "memory://",
        "CORS_ORIGINS": ["http://frontend.test"],
    })
    limiter.reset()  # Zähler aus vorherigen Tests löschen
    return app


class ApiClient:
    """
    Kleiner Helfer, der sich wie das Frontend verhält:
    holt einmal den CSRF-Token und schickt ihn bei jedem POST mit.
    """

    def __init__(self, client):
        self.client = client
        self.token = client.get("/api/csrf-token").get_json()["csrf_token"]

    def post(self, url, json=None):
        return self.client.post(url, json=json, headers={"X-CSRFToken": self.token})

    def get(self, url):
        return self.client.get(url)

    def register(self, username="alice", email="alice@example.com", password="sicheres-passwort"):
        return self.post("/api/register", {"username": username, "email": email, "password": password})

    def login(self, login="alice", password="sicheres-passwort"):
        return self.post("/api/login", {"login": login, "password": password})


@pytest.fixture
def api(app):
    return ApiClient(app.test_client())

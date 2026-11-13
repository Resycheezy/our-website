"""Tests für Registrierung, Login, Logout und /api/me."""

import sqlite3

import pytest


def _db_rows(app, sql, params=()):
    """Liest direkt aus der Test-Datenbank (an der API vorbei)."""
    path = app.config["DATABASE_URL"][len("sqlite:///"):]
    with sqlite3.connect(path) as conn:
        return conn.execute(sql, params).fetchall()


# --- Health ----------------------------------------------------------------

def test_health(api):
    r = api.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok", "database": "ok"}


# --- Registrierung ---------------------------------------------------------

def test_register_success(api, app):
    r = api.register()
    assert r.status_code == 201
    user = r.get_json()["user"]
    assert user["username"] == "alice"
    assert user["email"] == "alice@example.com"
    assert "password_hash" not in user  # Hash darf nie ans Frontend gehen
    # Nach der Registrierung ist man direkt eingeloggt
    assert api.get("/api/me").status_code == 200


def test_password_is_stored_hashed(api, app):
    api.register(password="mein-klartext-pw")
    (stored,) = _db_rows(app, "SELECT password_hash FROM users")[0]
    assert "mein-klartext-pw" not in stored
    assert stored.startswith("$argon2")


def test_email_is_lowercased(api):
    r = api.register(email="Alice@Example.COM")
    assert r.get_json()["user"]["email"] == "alice@example.com"


@pytest.mark.parametrize("payload, field", [
    ({"username": "ab", "email": "a@b.de", "password": "12345678"}, "username"),           # zu kurz
    ({"username": "böse name", "email": "a@b.de", "password": "12345678"}, "username"),    # Sonderzeichen
    ({"username": "alice", "email": "keine-mail", "password": "12345678"}, "email"),
    ({"username": "alice", "email": "a@b.de", "password": "kurz"}, "password"),
    ({"username": "alice", "email": "a@b.de", "password": "x" * 129}, "password"),
    ({"username": 123, "email": "a@b.de", "password": "12345678"}, "username"),            # falscher Typ
    ({"email": "a@b.de", "password": "12345678"}, "username"),                              # fehlt
])
def test_register_validation(api, payload, field):
    r = api.post("/api/register", payload)
    assert r.status_code == 400
    assert field in r.get_json()["fields"]


def test_register_requires_json(api):
    r = api.client.post("/api/register", data="kein json", headers={"X-CSRFToken": api.token})
    assert r.status_code == 400


def test_register_duplicate_username_case_insensitive(api):
    api.register(username="alice")
    r = api.register(username="ALICE", email="other@example.com")
    assert r.status_code == 409
    assert "username" in r.get_json()["fields"]


def test_register_duplicate_email(api):
    api.register(email="alice@example.com")
    r = api.register(username="bob", email="ALICE@example.com")
    assert r.status_code == 409
    assert "email" in r.get_json()["fields"]


# --- Login / Logout / me ---------------------------------------------------

def test_login_with_username_and_email(api):
    api.register()
    api.post("/api/logout")

    r = api.login(login="alice")
    assert r.status_code == 200
    assert r.get_json()["user"]["last_login"] is not None

    api.post("/api/logout")
    assert api.login(login="ALICE@example.com").status_code == 200


def test_login_wrong_password(api):
    api.register()
    api.post("/api/logout")
    r = api.login(password="falsches-passwort")
    assert r.status_code == 401
    assert api.get("/api/me").status_code == 401


def test_login_unknown_user_same_message(api):
    api.register()
    api.post("/api/logout")
    wrong_pw = api.login(password="falsches-passwort").get_json()
    unknown = api.login(login="gibtsnicht").get_json()
    # Gleiche Meldung -> Angreifer erfährt nicht, ob es den Benutzer gibt
    assert wrong_pw == unknown


def test_me_and_logout(api):
    assert api.get("/api/me").status_code == 401
    api.register()
    assert api.get("/api/me").get_json()["user"]["username"] == "alice"
    assert api.post("/api/logout").status_code == 200
    assert api.get("/api/me").status_code == 401


def test_me_after_account_deleted(api, app):
    api.register()
    path = app.config["DATABASE_URL"][len("sqlite:///"):]
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM users")
    assert api.get("/api/me").status_code == 401

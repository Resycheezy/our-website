"""Tests für Daten-Export und Konto löschen."""


def test_export_requires_login(api):
    assert api.get("/api/account/export").status_code == 401


def test_export_contains_user_data_but_no_hash(api):
    api.register()
    r = api.get("/api/account/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["Content-Disposition"]
    data = r.get_json()
    assert data["user"]["username"] == "alice"
    assert data["user"]["email"] == "alice@example.com"
    assert "password_hash" not in data["user"]
    assert "argon2" not in r.get_data(as_text=True)


def test_delete_requires_login(api):
    assert api.delete("/api/account", {"password": "x"}).status_code == 401


def test_delete_requires_csrf(api):
    api.register()
    r = api.client.delete("/api/account", json={"password": "sicheres-passwort"})
    assert r.status_code == 400


def test_delete_requires_password(api):
    api.register()
    r = api.delete("/api/account", {})
    assert r.status_code == 400
    assert "password" in r.get_json()["fields"]


def test_delete_wrong_password(api):
    api.register()
    r = api.delete("/api/account", {"password": "falsches-passwort"})
    assert r.status_code == 403
    # Konto besteht noch, man ist noch eingeloggt
    assert api.get("/api/me").status_code == 200


def test_delete_account(api):
    api.register()
    r = api.delete("/api/account", {"password": "sicheres-passwort"})
    assert r.status_code == 200
    assert api.get("/api/me").status_code == 401
    # Login geht nicht mehr, Name ist wieder frei
    assert api.login().status_code == 401
    assert api.register().status_code == 201

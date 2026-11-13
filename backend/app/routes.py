"""
Die Routen (URLs) der App.

  GET  /health           -> läuft die App, ist die DB erreichbar? (für nginx/Docker)
  GET  /api/csrf-token   -> CSRF-Token fürs Frontend holen
  POST /api/register     -> neues Konto anlegen
  POST /api/login        -> einloggen
  POST /api/logout       -> ausloggen
  GET  /api/me           -> wer ist gerade eingeloggt?
  GET  /api/account/export -> eigene Daten als JSON-Datei herunterladen
  DELETE /api/account    -> eigenes Konto löschen (mit Passwort-Bestätigung)
"""

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session
from flask_wtf.csrf import generate_csrf

from . import auth
from .db import IntegrityError, check_db, query
from .extensions import limiter

api = Blueprint("api", __name__, url_prefix="/api")
health_bp = Blueprint("health", __name__)

# Spalten, die wir ans Frontend zurückgeben. password_hash gehört NICHT dazu!
USER_COLUMNS = "id, username, email, created_at, last_login"


# --- Hilfsfunktionen -------------------------------------------------------

def _timestamp(value):
    """
    Wandelt einen Zeitstempel in ISO-Format um, z. B. "2026-11-13T10:15:00".
    PostgreSQL liefert datetime-Objekte, SQLite liefert Text.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value).replace(" ", "T")


def _user_json(row):
    """Macht aus einer Datenbankzeile das JSON-Objekt fürs Frontend."""
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "created_at": _timestamp(row["created_at"]),
        "last_login": _timestamp(row["last_login"]),
    }


def _json_body():
    """Liest den JSON-Body der Anfrage. Gibt None zurück, wenn es kein JSON-Objekt ist."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _validation_error(errors):
    return jsonify(error="Ungültige Eingabe", fields=errors), 400


def _login_user(user_id):
    """Merkt sich den Benutzer in der Session (= im signierten Cookie)."""
    session["user_id"] = user_id
    session.permanent = True  # Cookie bleibt PERMANENT_SESSION_LIFETIME lang gültig


# --- Health-Check ----------------------------------------------------------

@health_bp.get("/health")
def health():
    try:
        check_db()
    except Exception:
        current_app.logger.exception("Health-Check: Datenbank nicht erreichbar")
        return jsonify(status="error", database="unreachable"), 503
    return jsonify(status="ok", database="ok")


# --- API -------------------------------------------------------------------

@api.get("/csrf-token")
def csrf_token():
    """
    Das Frontend holt sich diesen Token einmal und schickt ihn bei jedem POST
    im Header "X-CSRFToken" mit.
    """
    return jsonify(csrf_token=generate_csrf())


@api.post("/register")
@limiter.limit(lambda: current_app.config["REGISTER_RATE_LIMIT"])
def register():
    data = _json_body()
    if data is None:
        return jsonify(error="JSON-Body erwartet"), 400

    clean, errors = auth.validate_registration(data)
    if errors:
        return _validation_error(errors)

    # Vorab prüfen, ob Name/E-Mail schon vergeben sind -> genaue Fehlermeldung fürs Formular.
    # Parametrisiert: die Werte stehen NICHT im SQL-Text, sondern im Tupel dahinter.
    existing = query(
        "SELECT username, email FROM users WHERE LOWER(username) = LOWER(%s) OR email = %s",
        (clean["username"], clean["email"]),
    )
    if existing:
        taken = {}
        for row in existing:
            if row["username"].lower() == clean["username"].lower():
                taken["username"] = "Benutzername ist bereits vergeben"
            if row["email"] == clean["email"]:
                taken["email"] = "E-Mail ist bereits registriert"
        return jsonify(error="Bereits vergeben", fields=taken), 409

    try:
        user = query(
            f"INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) "
            f"RETURNING {USER_COLUMNS}",
            (clean["username"], clean["email"], auth.hash_password(clean["password"])),
            one=True,
            commit=True,
        )
    except IntegrityError:
        # Falls zwei Leute genau gleichzeitig denselben Namen registrieren,
        # greift die UNIQUE-Regel der Datenbank.
        return jsonify(error="Benutzername oder E-Mail bereits vergeben"), 409

    _login_user(user["id"])  # nach der Registrierung direkt eingeloggt
    return jsonify(user=_user_json(user)), 201


@api.post("/login")
# Nur fehlgeschlagene Logins (401) zählen fürs Limit. Wer sich vertippt und dann
# richtig einloggt, wird nicht bestraft. Ein Angreifer, der rät, schon.
@limiter.limit(
    lambda: current_app.config["LOGIN_RATE_LIMIT"],
    deduct_when=lambda response: response.status_code == 401,
)
def login():
    data = _json_body()
    if data is None:
        return jsonify(error="JSON-Body erwartet"), 400

    clean, errors = auth.validate_login(data)
    if errors:
        return _validation_error(errors)

    # Login per Benutzername ODER E-Mail
    user = query(
        "SELECT id, password_hash FROM users WHERE LOWER(username) = LOWER(%s) OR email = LOWER(%s)",
        (clean["login"], clean["login"]),
        one=True,
    )

    # Auch wenn es den Benutzer nicht gibt, einen Hash prüfen (gleiche Antwortzeit, s. auth.py)
    password_hash = user["password_hash"] if user else auth.DUMMY_HASH
    password_ok = auth.verify_password(password_hash, clean["password"])

    if not user or not password_ok:
        # Absichtlich nicht verraten, ob Benutzername oder Passwort falsch war
        return jsonify(error="Benutzername/E-Mail oder Passwort falsch"), 401

    # Hash mit neueren Argon2-Einstellungen aktualisieren, falls nötig
    if auth.needs_rehash(user["password_hash"]):
        query(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (auth.hash_password(clean["password"]), user["id"]),
            commit=True,
        )

    row = query(
        f"UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s RETURNING {USER_COLUMNS}",
        (user["id"],),
        one=True,
        commit=True,
    )

    _login_user(user["id"])
    return jsonify(user=_user_json(row))


@api.post("/logout")
def logout():
    # Nur den Benutzer aus der Session entfernen. Der CSRF-Token bleibt erhalten,
    # damit das Frontend ohne neuen Token weitermachen kann.
    session.pop("user_id", None)
    return jsonify(message="Ausgeloggt")


@api.get("/me")
@auth.login_required
def me():
    user = query(f"SELECT {USER_COLUMNS} FROM users WHERE id = %s", (session["user_id"],), one=True)
    if user is None:
        # Konto wurde inzwischen gelöscht -> Session aufräumen
        session.pop("user_id", None)
        return jsonify(error="Nicht eingeloggt"), 401
    return jsonify(user=_user_json(user))


@api.get("/account/export")
@auth.login_required
def export_account():
    """
    "Meine Daten herunterladen" (Recht auf Datenübertragbarkeit, Art. 20 DSGVO).
    Liefert alle gespeicherten Daten des Kontos als JSON-Datei.
    """
    user = query(f"SELECT {USER_COLUMNS} FROM users WHERE id = %s", (session["user_id"],), one=True)
    if user is None:
        session.pop("user_id", None)
        return jsonify(error="Nicht eingeloggt"), 401

    response = jsonify(
        exported_at=datetime.now().isoformat(timespec="seconds"),
        user=_user_json(user),
        hinweis="Das Passwort wird nur als Hash gespeichert und deshalb nicht exportiert.",
    )
    # Browser soll die Antwort als Datei speichern statt sie anzuzeigen
    response.headers["Content-Disposition"] = 'attachment; filename="meine-daten.json"'
    return response


@api.delete("/account")
@auth.login_required
# Passwort-Raten über diese Route genauso begrenzen wie beim Login
@limiter.limit(
    lambda: current_app.config["LOGIN_RATE_LIMIT"],
    deduct_when=lambda response: response.status_code == 403,
)
def delete_account():
    """Löscht das eigene Konto endgültig. Zur Sicherheit muss das Passwort mitgeschickt werden."""
    data = _json_body() or {}
    password = data.get("password")
    if not isinstance(password, str) or not password:
        return _validation_error({"password": "Passwort zur Bestätigung angeben"})

    user = query("SELECT password_hash FROM users WHERE id = %s", (session["user_id"],), one=True)
    if user is None:
        session.pop("user_id", None)
        return jsonify(error="Nicht eingeloggt"), 401

    if not auth.verify_password(user["password_hash"], password):
        # 403 statt 401: man IST eingeloggt, nur das Bestätigungs-Passwort stimmt nicht
        return jsonify(error="Passwort ist falsch", fields={"password": "Passwort ist falsch"}), 403

    query("DELETE FROM users WHERE id = %s", (session["user_id"],), commit=True)
    session.pop("user_id", None)
    return jsonify(message="Konto gelöscht")

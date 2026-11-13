"""
Alles rund um Authentifizierung:
  - Passwörter hashen und prüfen (Argon2)
  - Eingaben validieren
  - Decorator @login_required für geschützte Routen
"""

import re
from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import jsonify, session

# --- Passwort-Hashing ------------------------------------------------------
#
# Argon2 ist ein absichtlich langsamer Hash-Algorithmus. Er fügt automatisch ein
# zufälliges "Salt" hinzu, d. h. zwei gleiche Passwörter ergeben unterschiedliche Hashes.
# Aus dem Hash kann man das Passwort nicht zurückrechnen.
_hasher = PasswordHasher()

# Ein Hash eines zufälligen Passworts. Wird beim Login benutzt, wenn es den Benutzer
# gar nicht gibt. So dauert ein Login mit falschem Benutzernamen genauso lange wie einer
# mit falschem Passwort, und ein Angreifer kann an der Antwortzeit nicht ablesen,
# welche Benutzernamen existieren.
DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password):
    return _hasher.hash(password)


def verify_password(password_hash, password):
    """True, wenn das Passwort zum Hash passt, sonst False."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash):
    """True, wenn der Hash mit veralteten Einstellungen erzeugt wurde."""
    return _hasher.check_needs_rehash(password_hash)


# --- Eingabe-Validierung ---------------------------------------------------

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
# Bewusst einfache Prüfung: etwas@etwas.etwas, ohne Leerzeichen
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN = 8
PASSWORD_MAX = 128


def _get_str(data, key):
    """Holt ein Feld aus dem JSON. Gibt None zurück, wenn es fehlt oder kein Text ist."""
    value = data.get(key)
    return value if isinstance(value, str) else None


def validate_registration(data):
    """
    Prüft die Daten für die Registrierung.
    Gibt (saubere_daten, fehler) zurück. fehler ist ein dict {feld: meldung}.
    """
    errors = {}

    username = (_get_str(data, "username") or "").strip()
    email = (_get_str(data, "email") or "").strip().lower()
    password = _get_str(data, "password") or ""  # Passwort nicht trimmen!

    if not USERNAME_RE.match(username):
        errors["username"] = "3–30 Zeichen, nur Buchstaben, Ziffern und _"
    if len(email) > 254 or not EMAIL_RE.match(email):
        errors["email"] = "Ungültige E-Mail-Adresse"
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        errors["password"] = f"Passwort muss {PASSWORD_MIN}–{PASSWORD_MAX} Zeichen lang sein"

    return {"username": username, "email": email, "password": password}, errors


def validate_login(data):
    """Prüft die Login-Daten. Gleiche Rückgabe wie validate_registration."""
    errors = {}

    login = (_get_str(data, "login") or "").strip()
    password = _get_str(data, "password") or ""

    if not 1 <= len(login) <= 254:
        errors["login"] = "Benutzername oder E-Mail angeben"
    if not 1 <= len(password) <= PASSWORD_MAX:
        errors["password"] = "Passwort angeben"

    return {"login": login, "password": password}, errors


# --- Geschützte Routen -----------------------------------------------------

def login_required(view):
    """Decorator: lässt die Route nur ausführen, wenn jemand eingeloggt ist."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Nicht eingeloggt"), 401
        return view(*args, **kwargs)

    return wrapper

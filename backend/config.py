"""
Konfiguration der App.

Alle Werte kommen aus Umgebungsvariablen (bzw. aus der Datei .env).
So steht kein Passwort und kein Secret im Code bzw. im Git-Repository.
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

# Liest die Datei .env ein (falls vorhanden) und setzt die Werte als Umgebungsvariablen.
load_dotenv()


def _bool(name, default):
    """Liest eine Umgebungsvariable als True/False ("1", "true", "yes" = True)."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # Mit diesem Schlüssel werden die Session-Cookies signiert.
    # Wer ihn kennt, könnte Cookies fälschen -> muss geheim und lang sein.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Datenbank:
    #   postgresql://user:passwort@host:5432/dbname  -> PostgreSQL
    #   sqlite:///dev.db                              -> SQLite-Datei (zum lokalen Testen)
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///dev.db")

    # --- Session-Cookies ---
    # Die Session wird als signiertes Cookie im Browser gespeichert (Flask-Standard).
    # Dadurch ist der Server "stateless": jede Instanz kann jede Anfrage bearbeiten.
    SESSION_COOKIE_HTTPONLY = True   # JavaScript kann das Cookie nicht lesen (Schutz vor XSS-Diebstahl)
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)  # Cookie nur über HTTPS senden
    SESSION_COOKIE_SAMESITE = "Lax"  # Cookie wird bei Anfragen von fremden Websites nicht mitgeschickt
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # --- CSRF ---
    # Flask-WTF erwartet bei POST-Anfragen den Header "X-CSRFToken".
    WTF_CSRF_TIME_LIMIT = None  # Token gilt so lange wie die Session

    # --- CORS ---
    # Kommagetrennte Liste der Frontend-Adressen, die auf die API zugreifen dürfen.
    CORS_ORIGINS = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "http://localhost:5500").split(",")
        if o.strip()
    ]

    # --- Rate-Limiting ---
    # memory:// reicht für eine Instanz. Bei mehreren Instanzen: redis://redis:6379/0,
    # damit alle Instanzen dieselben Zähler sehen.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "5 per minute;20 per hour")
    REGISTER_RATE_LIMIT = os.environ.get("REGISTER_RATE_LIMIT", "10 per hour")

    # Läuft die App hinter einem Proxy (nginx)? Dann steht die echte Client-IP im
    # Header X-Forwarded-For. ACHTUNG: Nur einschalten, wenn der Server NUR über den
    # Proxy erreichbar ist. Sonst kann ein Angreifer den Header selbst setzen und so
    # die IP-basierte Login-Sperre umgehen (unbegrenztes Passwort-Raten).
    TRUST_PROXY = _bool("TRUST_PROXY", False)

    # Anzahl der vertrauenswürdigen Proxys VOR der App. Wichtig gegen gefälschte
    # X-Forwarded-For-Header: es wird nur der n-t-letzte Eintrag als echte IP genommen.
    #   nur nginx            -> 1
    #   Cloudflare -> nginx  -> 2
    PROXY_HOPS = int(os.environ.get("PROXY_HOPS", "1"))

    # Hinter Cloudflare: die echte Client-IP steht im Header CF-Connecting-IP, den
    # Cloudflare bei jeder Anfrage selbst überschreibt (nicht fälschbar, solange der
    # Server nur Cloudflare-IPs annimmt). Dann zählt die Login-Sperre pro echtem Nutzer.
    TRUST_CF_CONNECTING_IP = _bool("TRUST_CF_CONNECTING_IP", False)

    # Maximale Größe einer Anfrage (16 KB reichen für Login/Registrierung locker).
    MAX_CONTENT_LENGTH = 16 * 1024

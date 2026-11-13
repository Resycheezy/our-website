"""
Datenbank-Zugriff ohne ORM: wir schreiben SQL selbst.

Unterstützt zwei Datenbanken, umschaltbar über DATABASE_URL:
  - PostgreSQL (psycopg)   -> für Docker / "Produktion"
  - SQLite (eingebaut)     -> zum schnellen lokalen Testen

WICHTIG: Alle Queries sind parametrisiert. Im SQL steht nur ein Platzhalter (%s),
die echten Werte werden getrennt an die Datenbank übergeben. Siehe README.md
("Warum parametrisierte Queries?").
"""

import sqlite3
from pathlib import Path

import psycopg
from flask import current_app, g
from psycopg.rows import dict_row

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema.sql"

# Damit man in routes.py beide Fehlerarten mit einem "except" abfangen kann
# (z. B. wenn ein UNIQUE-Feld schon vergeben ist).
IntegrityError = (sqlite3.IntegrityError, psycopg.IntegrityError)


def _is_postgres(url):
    return url.startswith(("postgresql://", "postgres://"))


def _connect(url):
    """Öffnet eine neue Verbindung zur Datenbank."""
    if _is_postgres(url):
        # dict_row: Ergebniszeilen kommen als Dictionary, z. B. row["username"]
        return psycopg.connect(url, row_factory=dict_row)

    if not url.startswith("sqlite:///"):
        raise ValueError("DATABASE_URL muss mit postgresql:// oder sqlite:/// beginnen")
    conn = sqlite3.connect(url[len("sqlite:///"):])
    conn.row_factory = sqlite3.Row  # Zeilen wie ein Dictionary ansprechbar
    return conn


def _adapt_sql(sql, url):
    """
    psycopg (PostgreSQL) nutzt %s als Platzhalter, sqlite3 nutzt ?.
    Wir schreiben überall %s und tauschen das für SQLite aus.
    Achtung: Hier wird nur der Platzhalter im SQL-Text getauscht, NICHT ein Wert
    eingesetzt. Die Werte gehen weiterhin getrennt an die Datenbank.
    """
    if _is_postgres(url):
        return sql
    return sql.replace("%s", "?")


def get_db():
    """
    Liefert die Datenbankverbindung für die aktuelle Anfrage.
    Pro Anfrage wird höchstens eine Verbindung geöffnet und am Ende wieder geschlossen.
    """
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE_URL"])
    return g.db


def close_db(_error=None):
    """Wird von Flask am Ende jeder Anfrage aufgerufen."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql, params=(), one=False, commit=False):
    """
    Führt eine SQL-Anweisung aus und gibt die Ergebniszeilen als Liste von dicts zurück.

      sql     SQL mit %s-Platzhaltern, z. B. "SELECT * FROM users WHERE id = %s"
      params  Die Werte für die Platzhalter als Tupel, z. B. (5,)
      one     True -> nur die erste Zeile zurückgeben (oder None)
      commit  True -> Änderungen dauerhaft speichern (bei INSERT/UPDATE/DELETE)
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(_adapt_sql(sql, current_app.config["DATABASE_URL"]), params)
        # Nur Anweisungen mit Ergebnis (SELECT oder ... RETURNING) haben eine "description"
        rows = [dict(row) for row in cur.fetchall()] if cur.description else []
        if commit:
            conn.commit()
    except Exception:
        # Bei einem Fehler die Transaktion zurückrollen, damit die Verbindung sauber bleibt
        conn.rollback()
        raise
    finally:
        cur.close()

    if one:
        return rows[0] if rows else None
    return rows


def init_db(url):
    """Führt schema.sql aus (legt Tabellen an, falls sie noch nicht existieren)."""
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    conn = _connect(url)
    try:
        if _is_postgres(url):
            with conn.cursor() as cur:
                # Wenn mehrere App-Instanzen gleichzeitig starten, würden sie gleichzeitig
                # CREATE TABLE ausführen. Ein "Advisory Lock" lässt sie nacheinander laufen.
                cur.execute("SELECT pg_advisory_xact_lock(4242)")
                cur.execute(schema)
            conn.commit()
        else:
            # SQLite kennt kein SERIAL -> durch die SQLite-Variante ersetzen
            schema = schema.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
            conn.executescript(schema)
            conn.commit()
    finally:
        conn.close()


def check_db():
    """Für /health: kann die Datenbank eine einfache Anfrage beantworten?"""
    return query("SELECT 1 AS ok", one=True) is not None


def init_app(app):
    """Bindet die Datenbank an die Flask-App."""
    app.teardown_appcontext(close_db)
    init_db(app.config["DATABASE_URL"])

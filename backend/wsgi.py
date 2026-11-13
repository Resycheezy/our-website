"""
Einstiegspunkt der App.

Lokal (Entwicklung):   python wsgi.py
In Docker (gunicorn):  gunicorn wsgi:app

WICHTIG: Der Debug-Modus zeigt bei einem Fehler interne Details (Stacktrace, SQL)
und bietet eine Konsole, über die man Code ausführen kann. Er darf NIEMALS öffentlich
erreichbar laufen. Deshalb ist er standardmäßig AUS und muss bewusst über die
Umgebungsvariable FLASK_DEBUG=true eingeschaltet werden (nur lokal!).
"""

import os

from app import create_app

app = create_app()


def _debug_enabled():
    """Debug nur, wenn FLASK_DEBUG ausdrücklich auf true/1/yes/on steht."""
    return os.environ.get("FLASK_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")


if __name__ == "__main__":
    # Standard: debug=False. Zum lokalen Entwickeln: FLASK_DEBUG=true python wsgi.py
    app.run(host="127.0.0.1", port=5000, debug=_debug_enabled())

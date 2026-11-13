"""
Einstiegspunkt der App.

Lokal (Entwicklung):   python wsgi.py
In Docker (gunicorn):  gunicorn wsgi:app
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True nur lokal! Zeigt Fehlerseiten mit Details und lädt bei Codeänderungen neu.
    app.run(host="127.0.0.1", port=5000, debug=True)

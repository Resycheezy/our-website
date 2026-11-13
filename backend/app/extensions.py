"""
Flask-Erweiterungen, die an mehreren Stellen gebraucht werden.
Sie werden hier einmal erstellt und in app/__init__.py mit der App verbunden.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

# Rate-Limiter: zählt Anfragen pro IP-Adresse
limiter = Limiter(key_func=get_remote_address)

# CSRF-Schutz: jede POST-Anfrage braucht einen gültigen Token im Header X-CSRFToken
csrf = CSRFProtect()

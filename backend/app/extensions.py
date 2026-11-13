"""
Flask-Erweiterungen, die an mehreren Stellen gebraucht werden.
Sie werden hier einmal erstellt und in app/__init__.py mit der App verbunden.
"""

from flask import current_app, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect


def client_ip():
    """
    Liefert die IP-Adresse, nach der das Rate-Limiting zählt.

    Hinter Cloudflare nehmen wir CF-Connecting-IP: diesen Header setzt Cloudflare
    selbst und überschreibt dabei alles, was der Client mitschickt. So kann ein
    Angreifer nicht bei jedem Versuch eine neue IP vortäuschen, um die Login-Sperre
    zu umgehen.

    Ohne Cloudflare nutzen wir get_remote_address(). Steht TRUST_PROXY=true, hat
    ProxyFix die echte IP schon aus X-Forwarded-For geholt (mit PROXY_HOPS begrenzt).
    """
    if current_app.config.get("TRUST_CF_CONNECTING_IP"):
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip
    return get_remote_address()


# Rate-Limiter: zählt Anfragen pro Client-IP (siehe client_ip)
limiter = Limiter(key_func=client_ip)

# CSRF-Schutz: jede POST-Anfrage braucht einen gültigen Token im Header X-CSRFToken
csrf = CSRFProtect()

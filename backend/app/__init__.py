"""
Hier wird die Flask-App zusammengebaut ("Application Factory").

create_app() erstellt jedes Mal eine neue, fertig konfigurierte App.
Das ist praktisch für Tests: jeder Test bekommt seine eigene App mit eigener Test-DB.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

from . import db
from .extensions import csrf, limiter
from .routes import api, health_bp


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY fehlt. Bitte in .env setzen (siehe .env.example).")

    # Hinter nginx kommt jede Anfrage scheinbar von nginx. ProxyFix liest stattdessen
    # die echte Client-IP aus X-Forwarded-For (wichtig fürs Rate-Limiting pro IP).
    # x_for = Anzahl vertrauenswürdiger Proxys: nur der n-t-letzte XFF-Eintrag gilt,
    # ältere (vom Client gefälschte) Einträge werden ignoriert.
    if app.config["TRUST_PROXY"]:
        hops = app.config["PROXY_HOPS"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    # CORS: Nur die in CORS_ORIGINS eingetragenen Frontends dürfen per JavaScript
    # auf /api/... zugreifen. supports_credentials=True erlaubt das Mitsenden von Cookies.
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
        allow_headers=["Content-Type", "X-CSRFToken"],
    )

    csrf.init_app(app)
    limiter.init_app(app)
    db.init_app(app)

    app.register_blueprint(api)
    app.register_blueprint(health_bp)

    _register_security_headers(app)
    _register_error_handlers(app)
    return app


def _register_security_headers(app):
    """
    Setzt bei JEDER Antwort schützende HTTP-Header. Die API liefert nur JSON,
    deshalb ist die Content-Security-Policy ganz streng (default-src 'none').
    Die statischen Frontend-Seiten liefert nginx aus und bekommt dort eigene Header.
    """

    @app.after_request
    def set_security_headers(response):
        # Browser soll den Content-Type nicht "erraten" (verhindert MIME-Tricks)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Seite darf nicht in einen fremden <iframe> eingebettet werden (Clickjacking)
        response.headers.setdefault("X-Frame-Options", "DENY")
        # Keine Referrer-Daten an andere Seiten weitergeben
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # JSON-Antwort braucht keinerlei aktive Inhalte
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        # HSTS nur über echtes HTTPS senden (sonst sperrt man sich lokal über http aus).
        # request.is_secure berücksichtigt X-Forwarded-Proto, wenn ProxyFix aktiv ist.
        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def _register_error_handlers(app):
    """Fehler immer als JSON zurückgeben, damit das Frontend sie einfach auswerten kann."""

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return jsonify(error="CSRF-Token fehlt oder ist ungültig"), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Nicht gefunden"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="Methode nicht erlaubt"), 405

    @app.errorhandler(413)
    def too_large(e):
        return jsonify(error="Anfrage zu groß"), 413

    @app.errorhandler(429)
    def too_many_requests(e):
        return jsonify(error="Zu viele Versuche, bitte später erneut versuchen"), 429

    @app.errorhandler(500)
    def server_error(e):
        return jsonify(error="Interner Serverfehler"), 500

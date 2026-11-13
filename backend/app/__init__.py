"""
Hier wird die Flask-App zusammengebaut ("Application Factory").

create_app() erstellt jedes Mal eine neue, fertig konfigurierte App.
Das ist praktisch für Tests: jeder Test bekommt seine eigene App mit eigener Test-DB.
"""

from flask import Flask, jsonify
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
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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

    _register_error_handlers(app)
    return app


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

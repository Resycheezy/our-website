"""Tests für die Sicherheitsfunktionen: CSRF, Rate-Limit, Cookies, CORS, SQL-Injection."""

from app import create_app
from app.extensions import limiter


def test_post_without_csrf_token_is_rejected(api):
    r = api.client.post("/api/register", json={
        "username": "alice", "email": "alice@example.com", "password": "sicheres-passwort",
    })
    assert r.status_code == 400
    assert "CSRF" in r.get_json()["error"]


def test_post_with_wrong_csrf_token_is_rejected(api):
    r = api.client.post("/api/login", json={"login": "a", "password": "b"},
                        headers={"X-CSRFToken": "gefälscht"})
    assert r.status_code == 400


def test_login_rate_limit(api):
    api.register()
    api.post("/api/logout")
    # Standard: 5 Fehlversuche pro Minute erlaubt, danach 429
    for _ in range(5):
        assert api.login(password="falsch-falsch").status_code == 401
    r = api.login(password="falsch-falsch")
    assert r.status_code == 429
    # Auch das richtige Passwort wird jetzt blockiert
    assert api.login().status_code == 429


def test_successful_logins_do_not_count_towards_limit(api):
    api.register()
    for _ in range(8):
        assert api.login().status_code == 200


def test_session_cookie_flags(app, tmp_path):
    secure_app = create_app({
        **app.config,
        "SESSION_COOKIE_SECURE": True,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'secure.db'}",
    })
    client = secure_app.test_client()
    r = client.get("/api/csrf-token", base_url="https://localhost")
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=Lax" in cookie


def test_cors_allows_only_our_frontend(api):
    ok = api.client.get("/api/me", headers={"Origin": "http://frontend.test"})
    assert ok.headers.get("Access-Control-Allow-Origin") == "http://frontend.test"
    assert ok.headers.get("Access-Control-Allow-Credentials") == "true"

    evil = api.client.get("/api/me", headers={"Origin": "http://evil.example"})
    assert "Access-Control-Allow-Origin" not in evil.headers


def test_sql_injection_in_login_does_not_work(api):
    api.register()
    api.post("/api/logout")
    # Klassischer Angriff: würde bei String-Verkettung die Passwort-Prüfung umgehen
    # bzw. mit "; DROP TABLE" die Tabelle löschen.
    for attack in ["' OR '1'='1", "alice' --", "x'; DROP TABLE users; --"]:
        r = api.login(login=attack, password="egal")
        assert r.status_code == 401
    # Tabelle existiert noch, Login funktioniert weiterhin
    assert api.login().status_code == 200


def test_unknown_route_returns_json_404(api):
    r = api.get("/api/gibtsnicht")
    assert r.status_code == 404
    assert r.get_json()["error"]


def test_security_headers_are_set(api):
    """Jede Antwort soll die schützenden Header tragen."""
    r = api.get("/api/csrf-token")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert "default-src 'none'" in r.headers.get("Content-Security-Policy", "")
    # Über http (Test) darf KEIN HSTS kommen, sonst sperrt man sich lokal aus
    assert "Strict-Transport-Security" not in r.headers


def test_hsts_only_over_https(app, tmp_path):
    secure_app = create_app({
        **app.config,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'hsts.db'}",
    })
    client = secure_app.test_client()
    r = client.get("/api/csrf-token", base_url="https://localhost")
    assert "max-age=" in r.headers.get("Strict-Transport-Security", "")


def test_cloudflare_mode_blocks_forwarded_for_spoofing(app, tmp_path):
    """
    Hinter Cloudflare zählt die Login-Sperre nach CF-Connecting-IP. Ein Angreifer,
    der bei jedem Versuch einen anderen X-Forwarded-For schickt, darf die Sperre
    damit NICHT umgehen.
    """
    cf_app = create_app({
        **app.config,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'cf.db'}",
        "TRUST_CF_CONNECTING_IP": True,
        "LOGIN_RATE_LIMIT": "5 per minute",
    })
    limiter.reset()
    client = cf_app.test_client()
    token = client.get("/api/csrf-token").get_json()["csrf_token"]
    h = {"X-CSRFToken": token}
    client.post("/api/register",
                json={"username": "opfer", "email": "o@x.de", "password": "sicheres-passwort"},
                headers=h)
    client.post("/api/logout", headers=h)

    # Angreifer: gleiche echte IP (CF-Connecting-IP), aber bei jedem Versuch neuer XFF
    attacker = {**h, "CF-Connecting-IP": "203.0.113.9"}
    codes = []
    for i in range(7):
        r = client.post("/api/login",
                        json={"login": "opfer", "password": "falsch"},
                        headers={**attacker, "X-Forwarded-For": f"10.0.0.{i}"})
        codes.append(r.status_code)
    # Nach 5 Fehlversuchen muss trotz wechselndem XFF die Sperre (429) greifen
    assert 429 in codes, codes


def test_proxy_hops_configurable(app):
    """Hinter Cloudflare->nginx müssen 2 Proxy-Schritte einstellbar sein."""
    assert app.config["PROXY_HOPS"] == 1  # Standard
    cfg = create_app({**app.config, "TRUST_PROXY": True, "PROXY_HOPS": 2})
    # ProxyFix wurde mit der konfigurierten Hop-Zahl umwickelt
    assert cfg.wsgi_app.x_for == 2

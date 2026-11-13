# Backend: Benutzerkonten (Flask + SQL)

Backend für unsere Website zum Thema Religion / Atheismus.
Es kümmert sich um Benutzerkonten: Registrierung, Login, Logout und „Wer bin ich?“.
Die Routen fürs Frontend stehen in [API.md](API.md).

## Aufbau

```
backend/
├── app/
│   ├── __init__.py    create_app(): baut die App zusammen (CORS, CSRF, Limiter, DB, Fehler)
│   ├── routes.py      die URLs: /api/register, /api/login, /api/logout, /api/me, /health
│   ├── auth.py        Passwort-Hashing (Argon2), Eingabe-Validierung, @login_required
│   ├── db.py          Datenbankzugriff mit reinem SQL (PostgreSQL oder SQLite)
│   └── extensions.py  Rate-Limiter und CSRF-Schutz
├── tests/             automatische Tests (pytest)
├── schema.sql         CREATE TABLE-Befehle, werden beim Start ausgeführt
├── config.py          liest alle Einstellungen aus Umgebungsvariablen / .env
├── wsgi.py            Startpunkt der App
├── Dockerfile         Bauplan für das App-Image
├── docker-compose.yml nginx + 3 App-Instanzen + PostgreSQL + Redis
├── nginx.conf         Load-Balancer-Konfiguration
└── .env.example       Vorlage für die geheimen Einstellungen
```

## Lokal starten (ohne Docker, mit SQLite)

```powershell
cd backend
uv venv                                  # oder: python -m venv .venv
uv pip install -r requirements.txt       # oder: .venv\Scripts\pip install -r requirements.txt
copy .env.example .env                   # danach SECRET_KEY in .env ändern!
.venv\Scripts\python wsgi.py
```

Die API läuft dann unter `http://localhost:5000`. Die Datenbank ist die Datei `dev.db`,
die beim ersten Start automatisch angelegt wird.

**Tests ausführen:**
```powershell
.venv\Scripts\python -m pytest -v
```

## Mit Docker starten (PostgreSQL + Load Balancer)

Voraussetzung: [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```powershell
cd backend
copy .env.example .env      # SECRET_KEY und POSTGRES_PASSWORD ändern!
docker compose up --build
```

Dann im Browser `http://localhost:8080` öffnen. nginx liefert das Frontend aus dem Ordner
`../frontend` aus und leitet `/api/...` an die Flask-Instanzen weiter.
Tipp: Wenn das Frontend `index.html` heißt, öffnet es sich direkt. Aktuell heißt die Datei
`main .html` (mit Leerzeichen); nginx ist so eingestellt, dass es auch die findet.

**Load Balancing sehen:** `http://localhost:8080/health` mehrmals neu laden und in den
Browser-DevTools (Netzwerk → Antwort-Header) auf `X-Served-By` achten: die IP wechselt
zwischen den drei Instanzen. Mit `docker compose stop app2` kannst du eine Instanz
„abschießen“: die Seite funktioniert trotzdem weiter.

---

## Erklärungen für die Präsentation

### Warum parametrisierte Queries? (SQL-Injection)

**Falsch** (String-Verkettung):
```python
sql = "SELECT * FROM users WHERE username = '" + username + "'"
```
Gibt ein Angreifer als Benutzername `' OR '1'='1` ein, entsteht:
```sql
SELECT * FROM users WHERE username = '' OR '1'='1'
```
`'1'='1'` ist immer wahr, die Abfrage liefert also alle Benutzer. Mit `'; DROP TABLE users; --`
könnte man sogar die Tabelle löschen. Die Eingabe wird hier **als SQL-Code** ausgeführt.

**Richtig** (so machen wir es überall):
```python
query("SELECT * FROM users WHERE username = %s", (username,))
```
Der SQL-Text mit dem Platzhalter `%s` und der Wert werden **getrennt** an die Datenbank
geschickt. Die Datenbank weiß dadurch: `%s` ist immer nur ein Wert, nie Code. Egal was der
Benutzer eintippt, es wird nur als Text verglichen. Der Test
`test_sql_injection_in_login_does_not_work` in `tests/test_security.py` probiert genau
diese Angriffe aus.

### Warum Passwörter hashen?

Wir speichern nie das Passwort, sondern nur einen **Argon2-Hash** (z. B. `$argon2id$v=19$...`).
- Ein Hash ist eine Einbahnstraße: aus dem Hash kann man das Passwort nicht zurückrechnen.
- Beim Login wird das eingegebene Passwort erneut gehasht und mit dem gespeicherten Hash verglichen.
- Argon2 ist absichtlich langsam und speicherhungrig, damit Angreifer nicht Milliarden
  Passwörter pro Sekunde durchprobieren können.
- Jeder Hash bekommt ein zufälliges **Salt**: Zwei Leute mit demselben Passwort haben trotzdem
  unterschiedliche Hashes.

Wird die Datenbank gestohlen, hat der Dieb also keine Passwörter im Klartext.

### Sessions und Cookies

Nach dem Login merkt sich der Server die Benutzer-ID in einem **signierten Cookie**.
„Signiert“ heißt: Der Inhalt ist mit dem `SECRET_KEY` unterschrieben. Ändert jemand das
Cookie (z. B. `user_id: 1` → `user_id: 2`), passt die Unterschrift nicht mehr und der Server
ignoriert es. Die Cookie-Einstellungen:

| Flag | Schützt vor |
|---|---|
| `HttpOnly` | JavaScript (z. B. eingeschleuster Schadcode, XSS) kann das Cookie nicht auslesen |
| `Secure` | Cookie wird nur über HTTPS gesendet, kann also nicht im WLAN mitgelesen werden |
| `SameSite=Lax` | Fremde Websites können keine POST-Anfragen mit unserem Cookie auslösen |

Nachteil signierter Cookies: Logout löscht das Cookie im Browser. Hat jemand vorher eine
Kopie gestohlen, bleibt die bis zum Ablauf (7 Tage) gültig. Wer das verhindern will,
speichert Sessions serverseitig in Redis. Für unser Projekt reicht die einfache Variante.

### CSRF-Schutz

CSRF („Cross-Site Request Forgery“): Eine böse Website bringt deinen Browser dazu, heimlich
eine Anfrage an unsere Seite zu schicken, und der Browser hängt dein Login-Cookie automatisch an.
Schutz: Jede POST-Anfrage muss einen geheimen **CSRF-Token** im Header `X-CSRFToken` mitschicken.
Den bekommt nur unser eigenes Frontend (über `GET /api/csrf-token`). Die fremde Seite kennt ihn nicht.

### Rate-Limiting

Ohne Limit könnte ein Angreifer automatisiert tausende Passwörter pro Minute ausprobieren
(**Brute Force**). Flask-Limiter erlaubt pro IP-Adresse nur **5 Fehlversuche pro Minute** und
**20 pro Stunde**, danach kommt `429 Too Many Requests`. Erfolgreiche Logins zählen nicht mit.

### CORS

Browser verbieten JavaScript standardmäßig, Anfragen an eine andere Adresse zu schicken.
Mit CORS erlauben wir gezielt nur **unserem** Frontend (Liste in `CORS_ORIGINS`) den Zugriff
auf `/api/...`. Jede andere Website wird vom Browser blockiert.

### Eingabe-Validierung

Jede Eingabe wird geprüft, bevor sie in die Datenbank kommt: Benutzername nur aus erlaubten
Zeichen, E-Mail im richtigen Format, Passwort 8–128 Zeichen, richtiger Datentyp. Zusätzlich
sind Anfragen auf 16 KB begrenzt.

### Load Balancing und „stateless“

```
Browser → nginx → app1 / app2 / app3 → PostgreSQL + Redis
```

- **nginx** nimmt alle Anfragen an und verteilt sie reihum (Round Robin) auf drei
  Flask-Instanzen. Fällt eine aus, schickt nginx die Anfragen an die anderen.
- Damit das funktioniert, muss die App **stateless** sein: Keine Instanz darf sich etwas im
  eigenen Arbeitsspeicher merken, das die anderen brauchen. Sonst wäre man nach dem Login bei
  app1 für app2 plötzlich wieder ausgeloggt.
  - Die **Session** steckt im signierten Cookie, das der Browser bei jeder Anfrage mitschickt.
    Jede Instanz kann es mit demselben `SECRET_KEY` prüfen.
  - Die **Benutzerdaten** liegen in der gemeinsamen PostgreSQL-Datenbank.
  - Die **Rate-Limit-Zähler** liegen in Redis. Sonst hätte jede Instanz eigene Zähler und ein
    Angreifer bekäme dreimal so viele Versuche.
- **gunicorn** ist ein Webserver für Python-Apps im Produktivbetrieb. Der eingebaute
  Flask-Server (`python wsgi.py`) ist nur für die Entwicklung gedacht.
- **/health** sagt Docker, ob eine Instanz gesund ist (antwortet und erreicht die DB).

### Secrets

Passwörter und Schlüssel stehen nur in `.env`, und die ist in `.gitignore` eingetragen,
landet also nie auf GitHub. `.env.example` zeigt, welche Werte nötig sind, ohne echte Werte.

## Für echten Betrieb noch nötig

- HTTPS (z. B. mit Let's Encrypt) und `SESSION_COOKIE_SECURE=true`
- Zeile `add_header X-Served-By ...` aus `nginx.conf` entfernen
- Regelmäßige Backups der PostgreSQL-Datenbank

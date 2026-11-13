# API-Dokumentation (für das Frontend)

Alle Routen sprechen **JSON**. Fehler kommen immer im Format `{"error": "..."}`,
bei Eingabefehlern zusätzlich mit `fields` (Meldung pro Formularfeld).

| Umgebung | Basis-URL |
|---|---|
| Lokal (`python wsgi.py`) | `http://localhost:5000` |
| Docker (`docker compose up`) | `http://localhost:8080` (Frontend und API unter derselben Adresse) |

---

## Das Wichtigste vorweg: Cookies und CSRF

1. **Login läuft über ein Cookie.** Der Browser speichert es automatisch. Du musst bei
   **jedem** `fetch` `credentials: "include"` angeben, sonst schickt der Browser das Cookie nicht mit.
2. **Jeder POST braucht einen CSRF-Token** im Header `X-CSRFToken`.
   Den Token holst du einmal beim Laden der Seite über `GET /api/csrf-token`.
   Fehlt er, kommt `400 {"error": "CSRF-Token fehlt oder ist ungültig"}`.

```js
const API = "http://localhost:5000"; // in Docker: "" (gleiche Adresse)

let csrfToken = null;

async function getCsrfToken() {
  const res = await fetch(`${API}/api/csrf-token`, { credentials: "include" });
  csrfToken = (await res.json()).csrf_token;
}

async function apiPost(path, body) {
  if (!csrfToken) await getCsrfToken();
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
    body: JSON.stringify(body ?? {}),
  });
  return { status: res.status, data: await res.json() };
}

async function apiGet(path) {
  const res = await fetch(`${API}${path}`, { credentials: "include" });
  return { status: res.status, data: await res.json() };
}

// Beispiel:
// const { status, data } = await apiPost("/api/login", { login: "max", password: "geheim123" });
// if (status === 200) console.log("Hallo", data.user.username);
```

> **Lokal testen:** Öffne das Frontend über `http://localhost:5500` (z. B. VS Code Live Server)
> und nutze als API `http://localhost:5000`, **nicht** `127.0.0.1`. Für den Browser sind
> `localhost` und `127.0.0.1` verschiedene Seiten, dann wird das Cookie nicht mitgeschickt.

---

## `GET /api/csrf-token`

Liefert den CSRF-Token für alle POST-Anfragen.

**Antwort `200`**
```json
{ "csrf_token": "IjQ1ZjM0YTk...Zw" }
```

---

## `POST /api/register`

Legt ein neues Konto an. Danach ist man **direkt eingeloggt**.

**Request**
```json
{
  "username": "max_mustermann",
  "email": "max@example.com",
  "password": "sicheres-passwort"
}
```

| Feld | Regeln |
|---|---|
| `username` | 3–30 Zeichen, nur `A–Z a–z 0–9 _`. Groß-/Kleinschreibung zählt bei der Eindeutigkeit nicht (`Max` = `max`) |
| `email` | gültige E-Mail, max. 254 Zeichen, wird kleingeschrieben gespeichert |
| `password` | 8–128 Zeichen |

**Antwort `201`**
```json
{
  "user": {
    "id": 1,
    "username": "max_mustermann",
    "email": "max@example.com",
    "created_at": "2026-11-13T12:18:59",
    "last_login": null
  }
}
```

**Fehler**

`400` Eingabe ungültig:
```json
{
  "error": "Ungültige Eingabe",
  "fields": {
    "username": "3–30 Zeichen, nur Buchstaben, Ziffern und _",
    "password": "Passwort muss 8–128 Zeichen lang sein"
  }
}
```

`409` bereits vergeben:
```json
{
  "error": "Bereits vergeben",
  "fields": { "email": "E-Mail ist bereits registriert" }
}
```

`429` zu viele Registrierungen von dieser IP (Standard: 10 pro Stunde).

---

## `POST /api/login`

Login mit Benutzername **oder** E-Mail.

**Request**
```json
{ "login": "max_mustermann", "password": "sicheres-passwort" }
```

**Antwort `200`**
```json
{
  "user": {
    "id": 1,
    "username": "max_mustermann",
    "email": "max@example.com",
    "created_at": "2026-11-13T12:18:59",
    "last_login": "2026-11-13T12:25:03"
  }
}
```

**Fehler**

`400` Feld fehlt:
```json
{ "error": "Ungültige Eingabe", "fields": { "password": "Passwort angeben" } }
```

`401` falsche Daten (absichtlich ohne Hinweis, *was* falsch war):
```json
{ "error": "Benutzername/E-Mail oder Passwort falsch" }
```

`429` zu viele **Fehlversuche** (Standard: 5 pro Minute, 20 pro Stunde pro IP):
```json
{ "error": "Zu viele Versuche, bitte später erneut versuchen" }
```
Der Header `Retry-After` sagt, wie viele Sekunden man warten muss.

---

## `POST /api/logout`

Loggt aus. Braucht keinen Body (aber den CSRF-Header).

**Antwort `200`**
```json
{ "message": "Ausgeloggt" }
```

---

## `GET /api/me`

Wer ist gerade eingeloggt? Gut geeignet, um beim Laden der Seite zu prüfen,
ob „Login“ oder „Hallo, Max“ angezeigt werden soll.

**Antwort `200`**
```json
{
  "user": {
    "id": 1,
    "username": "max_mustermann",
    "email": "max@example.com",
    "created_at": "2026-11-13T12:18:59",
    "last_login": "2026-11-13T12:25:03"
  }
}
```

**Antwort `401`** (nicht eingeloggt)
```json
{ "error": "Nicht eingeloggt" }
```

---

## `GET /api/account/export`

„Meine Daten herunterladen“. Nur eingeloggt. Antwort hat den Header
`Content-Disposition: attachment; filename="meine-daten.json"`.

**Antwort `200`**
```json
{
  "exported_at": "2026-11-13T14:02:11",
  "user": {
    "id": 1,
    "username": "max_mustermann",
    "email": "max@example.com",
    "created_at": "2026-11-13T12:18:59",
    "last_login": "2026-11-13T12:25:03"
  },
  "hinweis": "Das Passwort wird nur als Hash gespeichert und deshalb nicht exportiert."
}
```
**Antwort `401`**, wenn nicht eingeloggt.

---

## `DELETE /api/account`

Löscht das eigene Konto **endgültig**. Nur eingeloggt, braucht den CSRF-Header
und das Passwort zur Bestätigung. Danach ist man ausgeloggt.

**Request**
```json
{ "password": "sicheres-passwort" }
```

**Antwort `200`**
```json
{ "message": "Konto gelöscht" }
```

**Fehler**

`400` Passwort fehlt:
```json
{ "error": "Ungültige Eingabe", "fields": { "password": "Passwort zur Bestätigung angeben" } }
```

`403` Passwort falsch (man bleibt eingeloggt):
```json
{ "error": "Passwort ist falsch", "fields": { "password": "Passwort ist falsch" } }
```

`401` nicht eingeloggt, `429` zu viele Fehlversuche (gleiches Limit wie beim Login).

---

## `GET /health`

Für den Load Balancer / Docker. Fürs Frontend normalerweise nicht nötig.

**Antwort `200`**
```json
{ "status": "ok", "database": "ok" }
```
**Antwort `503`**, wenn die Datenbank nicht erreichbar ist.

---

## Statuscodes im Überblick

| Code | Bedeutung |
|---|---|
| 200 | OK |
| 201 | Konto angelegt |
| 400 | Eingabe ungültig, kein JSON oder CSRF-Token fehlt |
| 401 | Nicht eingeloggt / Login falsch |
| 403 | Bestätigungs-Passwort beim Konto löschen falsch |
| 404 | Route gibt es nicht |
| 409 | Benutzername/E-Mail schon vergeben |
| 413 | Anfrage zu groß (> 16 KB) |
| 429 | Zu viele Versuche |
| 500 | Fehler im Backend |

/*
 * api.js – die EINZIGE Stelle, die mit dem Backend spricht.
 * Alle Routen sind in backend/API.md beschrieben.
 *
 * Wichtig:
 *  - credentials: "include" -> der Browser schickt das Session-Cookie mit
 *  - jeder POST/DELETE braucht den CSRF-Token im Header "X-CSRFToken"
 */

/*
 * Adresse des Backends.
 *  - Docker (nginx, Port 8080): Frontend und API laufen unter derselben Adresse -> ""
 *  - Lokal mit VS Code Live Server (Port 5500) + "python wsgi.py" (Port 5000):
 *    gleicher Hostname wie die Seite, nur Port 5000. Sonst schickt der Browser
 *    das Cookie nicht mit (localhost und 127.0.0.1 zählen als verschiedene Seiten).
 */
export const API_BASE = location.port === "5500" ? `http://${location.hostname}:5000` : "";

let csrfToken = null;

/** Holt den CSRF-Token vom Backend (nur einmal, danach aus dem Zwischenspeicher). */
async function getCsrfToken(forceNew = false) {
  if (csrfToken && !forceNew) return csrfToken;
  const res = await fetch(`${API_BASE}/api/csrf-token`, { credentials: "include" });
  const data = await res.json();
  csrfToken = data.csrf_token;
  return csrfToken;
}

/**
 * Schickt eine Anfrage ans Backend.
 * Gibt immer ein Objekt { ok, status, data } zurück, auch bei Fehlern.
 * So muss nicht jede Seite selbst try/catch schreiben.
 */
async function request(method, path, body, isRetry = false) {
  const options = {
    method,
    credentials: "include",
    headers: {},
  };

  // Ändernde Anfragen brauchen den CSRF-Token
  if (method !== "GET") {
    options.headers["X-CSRFToken"] = await getCsrfToken();
  }
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch {
    // Netzwerkfehler: Backend läuft nicht oder ist nicht erreichbar
    return {
      ok: false,
      status: 0,
      data: { error: "Der Server ist gerade nicht erreichbar. Bitte später erneut versuchen." },
    };
  }

  let data = {};
  try {
    data = await res.json();
  } catch {
    // Antwort war kein JSON (sollte beim Backend nicht vorkommen)
  }

  // Ist der Token abgelaufen (z. B. Cookie gelöscht), einmal neu holen und wiederholen
  if (res.status === 400 && data.error?.includes("CSRF") && !isRetry) {
    await getCsrfToken(true);
    return request(method, path, body, true);
  }

  return { ok: res.ok, status: res.status, data };
}

// --- Die einzelnen Routen --------------------------------------------------

/** POST /api/register – Antwort 201 { user } */
export function register(username, email, password) {
  return request("POST", "/api/register", { username, email, password });
}

/** POST /api/login – "login" ist Benutzername ODER E-Mail */
export function login(loginName, password) {
  return request("POST", "/api/login", { login: loginName, password });
}

/** POST /api/logout */
export function logout() {
  return request("POST", "/api/logout", {});
}

/** GET /api/me – 200 { user } wenn eingeloggt, sonst 401 */
export function me() {
  return request("GET", "/api/me");
}

/** GET /api/account/export – alle eigenen Daten als JSON */
export function exportAccount() {
  return request("GET", "/api/account/export");
}

/** DELETE /api/account – braucht das Passwort zur Bestätigung */
export function deleteAccount(password) {
  return request("DELETE", "/api/account", { password });
}

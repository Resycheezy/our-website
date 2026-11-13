/*
 * forms.js – Logik für login.html, register.html und konto.html.
 * Welche Seite gerade offen ist, steht im <body data-page="...">.
 *
 * Die Prüfregeln entsprechen genau denen im Backend (backend/app/auth.py).
 * Das Backend prüft trotzdem nochmal, denn Frontend-Prüfungen kann man umgehen.
 */

import * as api from "./api.js";
import { currentUser, showAuthState } from "./main.js";

// Gleiche Regeln wie im Backend
const USERNAME_RE = /^[A-Za-z0-9_]{3,30}$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PASSWORD_MIN = 8;
const PASSWORD_MAX = 128;

const page = document.body.dataset.page;


// --- Hilfsfunktionen für Fehlermeldungen ----------------------------------

/** Zeigt unter einem Feld eine Fehlermeldung an (oder entfernt sie bei message = ""). */
function setFieldError(form, name, message) {
  const input = form.elements[name];
  const errorEl = form.querySelector(`#${name}-error`);
  if (!input || !errorEl) return;
  errorEl.textContent = message;
  input.setAttribute("aria-invalid", message ? "true" : "false");
}

/** Meldung oben im Formular. type: "error" oder "success". */
function setAlert(form, message, type = "error") {
  const alert = form.querySelector(".form-alert");
  alert.textContent = message;
  alert.classList.toggle("form-alert--success", type === "success");
}

function clearErrors(form) {
  form.querySelectorAll(".field-error").forEach((el) => (el.textContent = ""));
  form.querySelectorAll("[aria-invalid]").forEach((el) => el.setAttribute("aria-invalid", "false"));
  setAlert(form, "");
}

/**
 * Zeigt Fehler an und setzt den Fokus auf das erste fehlerhafte Feld,
 * damit auch Screenreader-Nutzer*innen sofort wissen, wo das Problem ist.
 */
function showErrors(form, errors) {
  const names = Object.keys(errors);
  names.forEach((name) => setFieldError(form, name, errors[name]));
  if (names.length) form.elements[names[0]]?.focus();
}

/** Knopf während des Sendens sperren, damit man nicht doppelt klickt. */
function setBusy(form, busy, busyText) {
  const button = form.querySelector('button[type="submit"]');
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? busyText : button.dataset.label;
}

/** Freundliche Texte für Antworten, bei denen das Backend keine Feld-Fehler liefert. */
function friendlyError(status, data) {
  if (status === 429) return "Zu viele Versuche. Bitte warte kurz und versuche es dann erneut.";
  if (status === 0) return data.error; // Server nicht erreichbar
  if (status >= 500) return "Da ist auf dem Server etwas schiefgelaufen. Bitte später erneut versuchen.";
  return data.error || "Etwas ist schiefgelaufen.";
}

/** Formatiert einen Zeitstempel aus dem Backend, z. B. "13.11.2026, 12:18 Uhr". */
function formatDate(iso) {
  if (!iso) return "–";
  const date = new Date(iso);
  return (
    date.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" }) + " Uhr"
  );
}


// --- Registrierung -----------------------------------------------------------

function validateRegister(form) {
  const errors = {};
  const username = form.elements.username.value.trim();
  const email = form.elements.email.value.trim();
  const password = form.elements.password.value;
  const password2 = form.elements.password2.value;

  if (!username) errors.username = "Bitte gib einen Benutzernamen ein.";
  else if (!USERNAME_RE.test(username))
    errors.username = "3–30 Zeichen, nur Buchstaben (ohne Umlaute), Ziffern und _.";

  if (!email) errors.email = "Bitte gib deine E-Mail-Adresse ein.";
  else if (email.length > 254 || !EMAIL_RE.test(email))
    errors.email = "Das sieht nicht nach einer gültigen E-Mail-Adresse aus.";

  if (password.length < PASSWORD_MIN)
    errors.password = `Das Passwort muss mindestens ${PASSWORD_MIN} Zeichen lang sein.`;
  else if (password.length > PASSWORD_MAX)
    errors.password = `Das Passwort darf höchstens ${PASSWORD_MAX} Zeichen lang sein.`;

  if (!errors.password && password !== password2)
    errors.password2 = "Die Passwörter stimmen nicht überein.";

  if (!form.elements.terms.checked)
    errors.terms = "Bitte bestätige, dass du die Datenschutzerklärung und die Nutzungsbedingungen gelesen hast.";

  return errors;
}

async function initRegister() {
  const form = document.getElementById("register-form");

  // Wer schon eingeloggt ist, braucht kein neues Konto
  if (await currentUser) {
    window.location.replace("konto.html");
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault(); // Seite nicht neu laden, wir schicken die Daten per fetch
    clearErrors(form);

    const errors = validateRegister(form);
    if (Object.keys(errors).length) {
      setAlert(form, "Bitte prüfe die markierten Felder.");
      showErrors(form, errors);
      return;
    }

    setBusy(form, true, "Konto wird erstellt …");
    const { ok, status, data } = await api.register(
      form.elements.username.value.trim(),
      form.elements.email.value.trim(),
      form.elements.password.value
    );
    setBusy(form, false);

    if (ok) {
      // Das Backend loggt nach der Registrierung direkt ein
      window.location.href = "konto.html?neu=1";
      return;
    }

    // 400 = Eingabe ungültig, 409 = Name/E-Mail schon vergeben -> Feld-Fehler aus dem Backend
    if (data.fields) {
      setAlert(form, status === 409 ? "Benutzername oder E-Mail ist schon vergeben." : "Bitte prüfe die markierten Felder.");
      showErrors(form, data.fields);
    } else {
      setAlert(form, friendlyError(status, data));
    }
  });
}


// --- Login -----------------------------------------------------------------------

async function initLogin() {
  const form = document.getElementById("login-form");

  if (await currentUser) {
    window.location.replace("konto.html");
    return;
  }

  // Hinweis nach dem Löschen des Kontos
  if (new URLSearchParams(location.search).has("geloescht")) {
    setAlert(form, "Dein Konto wurde gelöscht.", "success");
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors(form);

    const loginName = form.elements.login.value.trim();
    const password = form.elements.password.value;
    const errors = {};
    if (!loginName) errors.login = "Bitte gib deinen Benutzernamen oder deine E-Mail ein.";
    if (!password) errors.password = "Bitte gib dein Passwort ein.";
    if (Object.keys(errors).length) {
      showErrors(form, errors);
      return;
    }

    setBusy(form, true, "Anmelden …");
    const { ok, status, data } = await api.login(loginName, password);
    setBusy(form, false);

    if (ok) {
      window.location.href = "konto.html";
      return;
    }

    if (status === 401) {
      setAlert(form, "Benutzername/E-Mail oder Passwort ist falsch.");
      form.elements.password.value = "";
      form.elements.password.focus();
    } else if (data.fields) {
      showErrors(form, data.fields);
    } else {
      setAlert(form, friendlyError(status, data));
    }
  });
}


// --- Konto ----------------------------------------------------------------------

async function initAccount() {
  const user = await currentUser;

  // Nur für eingeloggte Nutzer*innen
  if (!user) {
    window.location.replace("login.html");
    return;
  }

  // Profildaten eintragen (textContent -> sicher gegen XSS)
  document.getElementById("acc-username").textContent = user.username;
  document.getElementById("acc-email").textContent = user.email;
  document.getElementById("acc-created").textContent = formatDate(user.created_at);
  document.getElementById("acc-last-login").textContent = formatDate(user.last_login);
  document.getElementById("account-content").hidden = false;
  document.getElementById("account-loading").hidden = true;

  if (new URLSearchParams(location.search).has("neu")) {
    document.getElementById("welcome").hidden = false;
  }

  // "Meine Daten herunterladen"
  const exportButton = document.getElementById("export-button");
  const exportStatus = document.getElementById("export-status");
  exportButton.addEventListener("click", async () => {
    exportButton.disabled = true;
    exportStatus.textContent = "";
    const { ok, status, data } = await api.exportAccount();
    exportButton.disabled = false;

    if (!ok) {
      exportStatus.textContent = friendlyError(status, data);
      return;
    }

    // Die Daten als Datei "meine-daten.json" speichern
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "meine-daten.json";
    link.click();
    URL.revokeObjectURL(link.href);
    exportStatus.textContent = "Download gestartet: meine-daten.json";
  });

  // "Konto löschen"
  const deleteForm = document.getElementById("delete-form");
  deleteForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors(deleteForm);

    const password = deleteForm.elements.password.value;
    if (!password) {
      showErrors(deleteForm, { password: "Bitte gib zur Bestätigung dein Passwort ein." });
      return;
    }

    // Letzte Sicherheitsabfrage
    const sure = window.confirm(
      "Willst du dein Konto wirklich endgültig löschen? Das kann nicht rückgängig gemacht werden."
    );
    if (!sure) return;

    setBusy(deleteForm, true, "Wird gelöscht …");
    const { ok, status, data } = await api.deleteAccount(password);
    setBusy(deleteForm, false);

    if (ok) {
      showAuthState(null);
      window.location.href = "login.html?geloescht=1";
      return;
    }

    if (status === 401) {
      window.location.replace("login.html");
    } else if (data.fields) {
      showErrors(deleteForm, data.fields); // z. B. "Passwort ist falsch"
    } else {
      setAlert(deleteForm, friendlyError(status, data));
    }
  });
}


// --- Start: passende Funktion für die aktuelle Seite -------------------------
if (page === "register") initRegister();
if (page === "login") initLogin();
if (page === "konto") initAccount();

/*
 * main.js – läuft auf JEDER Seite.
 *  1. Header: zeigt "Login/Registrieren" oder "Hallo, <Name>"
 *  2. Handy-Menü auf- und zuklappen
 *  3. Linie unter dem Header beim Scrollen
 *  4. Sanftes Einblenden beim Scrollen
 *  5. Cookie-Hinweis
 */

import * as api from "./api.js";

// Signal an das CSS: JavaScript ist aktiv (für Animationen und das Handy-Menü)
document.documentElement.classList.add("js");


// --- 1. Header: eingeloggt oder nicht? ------------------------------------

/**
 * Fragt das Backend, wer eingeloggt ist, und passt den Header an.
 * Andere Skripte (forms.js) können auf das Ergebnis warten: await currentUser
 */
export const currentUser = loadCurrentUser();

async function loadCurrentUser() {
  const { ok, data } = await api.me();
  const user = ok ? data.user : null;
  showAuthState(user);
  return user;
}

/** Blendet Elemente mit data-auth="guest" bzw. data-auth="user" ein oder aus. */
export function showAuthState(user) {
  document.querySelectorAll('[data-auth="guest"]').forEach((el) => (el.hidden = Boolean(user)));
  document.querySelectorAll('[data-auth="user"]').forEach((el) => (el.hidden = !user));
  document.querySelectorAll("[data-username]").forEach((el) => {
    // textContent statt innerHTML: der Name wird nie als HTML ausgeführt (Schutz vor XSS)
    el.textContent = user ? user.username : "";
  });
}

// Logout-Knöpfe (im Header und auf der Kontoseite)
document.querySelectorAll("[data-logout]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    await api.logout();
    // Zur Startseite. Der Link im Header zeigt immer auf die richtige Datei.
    window.location.href = document.querySelector(".brand").href;
  });
});


// --- 2. Handy-Menü -------------------------------------------------------------

const navToggle = document.querySelector(".nav-toggle");
const nav = document.getElementById("site-nav");

if (navToggle && nav) {
  navToggle.addEventListener("click", () => {
    const open = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!open));
    navToggle.textContent = open ? "Menü" : "Schließen";
    nav.classList.toggle("is-open", !open);
  });

  // Escape schließt das Menü wieder (Tastaturbedienung)
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.classList.contains("is-open")) {
      navToggle.click();
      navToggle.focus();
    }
  });
}


// --- 3. Header-Linie beim Scrollen ------------------------------------------

const header = document.querySelector(".site-header");
const updateHeader = () => header?.classList.toggle("is-scrolled", window.scrollY > 8);
window.addEventListener("scroll", updateHeader, { passive: true });
updateHeader();


// --- 4. Einblenden beim Scrollen -----------------------------------------------

const revealElements = document.querySelectorAll(".reveal");

if ("IntersectionObserver" in window) {
  // Der Observer meldet, wenn ein Element in den sichtbaren Bereich kommt
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target); // nur einmal animieren
        }
      });
    },
    { threshold: 0.15 }
  );
  revealElements.forEach((el) => observer.observe(el));
} else {
  // Sehr alte Browser: einfach alles anzeigen
  revealElements.forEach((el) => el.classList.add("is-visible"));
}


// --- 5. Cookie-Hinweis -----------------------------------------------------------
// Kein Einwilligungs-Banner nötig, weil wir nur technisch notwendige Cookies nutzen.
// Wer den Hinweis schließt, bekommt ihn nicht mehr angezeigt. Das merken wir uns im
// localStorage des Browsers (steht auch auf der Seite cookies.html).

const NOTICE_KEY = "cookie-hinweis-geschlossen";
const notice = document.querySelector(".cookie-notice");

function noticeDismissed() {
  try {
    return localStorage.getItem(NOTICE_KEY) === "1";
  } catch {
    return false; // localStorage gesperrt (z. B. privater Modus)
  }
}

if (notice && !noticeDismissed()) {
  notice.hidden = false;
  notice.querySelector("[data-cookie-close]").addEventListener("click", () => {
    notice.hidden = true;
    try {
      localStorage.setItem(NOTICE_KEY, "1");
    } catch {
      // nicht schlimm, dann erscheint der Hinweis beim nächsten Mal wieder
    }
  });
}

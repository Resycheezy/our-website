# Frontend: Atheismus verstehen

Reines HTML, CSS und JavaScript, ohne Framework, ohne externe Dienste (kein CDN,
keine Google Fonts). Spricht mit dem Flask-Backend in `../backend` (Routen: [API.md](../backend/API.md)).

## Aufbau

```
frontend/
├── index.html              Startseite
├── pages/
│   ├── geschichte.html     Zeitleiste: Antike, Aufklärung, Moderne, heute
│   ├── positionen.html     Vergleich der Weltanschauungen
│   ├── quellen.html        Quellenverzeichnis
│   ├── login.html          Login-Formular
│   ├── register.html       Registrierung (mit Pflicht-Checkbox)
│   ├── konto.html          Profil, Daten-Export, Konto löschen (nur eingeloggt)
│   ├── datenschutz.html    ┐ Rechtstexte
│   ├── nutzungsbedingungen.html │
│   └── cookies.html        ┘
├── css/style.css           Gesamtes Design; alle Farben/Abstände als Variablen in :root
├── js/
│   ├── api.js              Alle Anfragen ans Backend (fetch mit credentials: "include")
│   ├── main.js             Läuft überall: Header-Login-Status, Handy-Menü, Animationen, Cookie-Hinweis
│   └── forms.js            Login, Registrierung und Konto
├── fonts/                  Schrift Inter (lokal) + Lizenz (OFL.txt)
└── img/                    Eigene SVG-Grafiken
```

Header und Footer stehen in jeder HTML-Datei. Wer z. B. einen Footer-Link ändert,
muss das in allen 10 Dateien tun (Suchen & Ersetzen in VS Code: `Strg+Umschalt+H`).

## Lokal starten

Die Seiten müssen über einen Webserver laufen. Mit Doppelklick (`file://`) funktionieren
Cookies und JavaScript-Module nicht.

1. **Backend** starten (siehe `../backend/README.md`): `python wsgi.py` → Port 5000
2. **Frontend** mit der VS-Code-Erweiterung „Live Server“ öffnen → Port 5500
   (oder: `python -m http.server 5500 -d frontend` im Projektordner)
3. Im Browser `http://localhost:5500/...` öffnen

`js/api.js` erkennt den Port 5500 und schickt die Anfragen dann an Port 5000 mit demselben
Hostnamen. Mit Docker (`docker compose up` im Backend-Ordner) liefert nginx Frontend und API
unter `http://localhost:8080` gemeinsam aus.

## Was wo eintragen?

| Was | Wo |
|---|---|
| Namen, Schule, Fach, Schuljahr | Footer in allen Seiten |
| Zahlen aktualisieren (Stand: Ende 2024 bzw. 2020) | `index.html` („In Zahlen“), `geschichte.html` und die Quelle in `quellen.html` |
| Farben, Schrift, Abstände | `css/style.css`, Abschnitt 2 (`:root`) |

## Barrierefreiheit

- Skip-Link „Zum Inhalt springen“ (erscheint beim ersten Druck auf Tab)
- Semantisches HTML (`header`, `nav`, `main`, `footer`, Überschriften-Hierarchie, Tabellen mit `th scope`)
- Sichtbarer Fokus-Rahmen, alles per Tastatur bedienbar, Handy-Menü schließt mit Escape
- Fehlermeldungen sind mit den Feldern verknüpft (`aria-describedby`, `aria-invalid`) und
  werden vorgelesen (`role="alert"`); der Fokus springt aufs erste fehlerhafte Feld
- Kontraste nach WCAG AA, Text mindestens 4,5 : 1
- Bei „Bewegung reduzieren“ (`prefers-reduced-motion`) gibt es keine Animationen

## Sicherheit im Frontend

- Benutzernamen werden immer mit `textContent` eingefügt, nie mit `innerHTML` → kein XSS
- Formulare nutzen `method="post"`, damit Passwörter auch ohne JavaScript nie in der URL landen
- Die Prüfungen im Frontend sind nur Komfort. Das Backend prüft alles noch einmal.

## Vor der Veröffentlichung

- [ ] Rechtstexte von einer fachkundigen Person prüfen lassen (Hinweis oben auf den Seiten danach entfernen)
- [ ] Server-Logs wirklich nach der in der Datenschutzerklärung genannten Frist löschen
      (Docker speichert Logs standardmäßig unbegrenzt → Log-Rotation einrichten)
- [ ] HTTPS einrichten und im Backend `SESSION_COOKIE_SECURE=true` setzen

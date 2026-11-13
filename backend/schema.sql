-- Datenbank-Schema. Wird bei jedem Start der App ausgeführt.
-- "IF NOT EXISTS" sorgt dafür, dass bestehende Tabellen/Daten nicht überschrieben werden.
--
-- Diese Datei funktioniert mit PostgreSQL UND SQLite.
-- Einzige Ausnahme: "SERIAL" (automatisch hochzählende ID) kennt nur PostgreSQL.
-- Für SQLite ersetzt app/db.py das automatisch durch "INTEGER PRIMARY KEY AUTOINCREMENT".

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(30)  NOT NULL UNIQUE,
    email         VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,          -- nur der Argon2-Hash, nie das Passwort!
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login    TIMESTAMP                        -- NULL, bis sich jemand zum ersten Mal einloggt
);

-- Benutzernamen sollen ohne Rücksicht auf Groß-/Kleinschreibung eindeutig sein:
-- "Max" und "max" dürfen nicht beide existieren.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower ON users (LOWER(username));

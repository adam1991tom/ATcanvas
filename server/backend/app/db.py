import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv('AT_CANVAS_DB', '/data/at-canvas.db')
MEDIA_DIR = Path(os.getenv('AT_CANVAS_MEDIA', '/data/media'))

# secrets: internal values that must never be returned by a generic settings read
#          (session signing key, OAuth client secrets/tokens once calendar sync lands)
# settings: user-facing config, safe to expose via GET /api/settings
SCHEMA = """
CREATE TABLE IF NOT EXISTS secrets(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS layouts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    width INTEGER DEFAULT 1920,
    height INTEGER DEFAULT 1080,
    background TEXT DEFAULT '#101318',
    created_at INTEGER,
    updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS layers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layout_id INTEGER NOT NULL REFERENCES layouts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    x REAL DEFAULT 5,
    y REAL DEFAULT 5,
    w REAL DEFAULT 30,
    h REAL DEFAULT 20,
    z INTEGER DEFAULT 1,
    visible INTEGER DEFAULT 1,
    locked INTEGER DEFAULT 0,
    opacity REAL DEFAULT 1,
    config TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS displays(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    layout_id INTEGER REFERENCES layouts(id) ON DELETE SET NULL,
    test_mode INTEGER DEFAULT 1,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS people(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#6aa7ff',
    avatar TEXT DEFAULT '',
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS lists(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL DEFAULT 'generic',
    name TEXT NOT NULL,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS list_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    done INTEGER DEFAULT 0,
    assignee_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    points INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS rewards(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    point_cost INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS redemptions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    reward_id INTEGER NOT NULL REFERENCES rewards(id) ON DELETE CASCADE,
    redeemed_at INTEGER
);
"""


def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

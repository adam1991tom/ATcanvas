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

CREATE TABLE IF NOT EXISTS media(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime TEXT,
    size INTEGER,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS notes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT DEFAULT '',
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS meal_plan(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    slot TEXT NOT NULL DEFAULT 'dinner',
    text TEXT NOT NULL DEFAULT '',
    UNIQUE(date, slot)
);

CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    effect TEXT NOT NULL DEFAULT 'none',
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS schedules(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS schedule_blocks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'layout',
    target TEXT DEFAULT ''
);
"""


def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _migrate(conn):
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(displays)').fetchall()}
    if 'schedule_id' not in cols:
        conn.execute('ALTER TABLE displays ADD COLUMN schedule_id INTEGER REFERENCES schedules(id) ON DELETE SET NULL')
    if 'orientation' not in cols:
        # Degrees clockwise the rendered layout is rotated before being scaled to
        # fit the physical screen - lets a 1920x1080-authored layout fill a
        # portrait-mounted screen (90/270) or run upside down (180) without
        # redesigning it.
        conn.execute("ALTER TABLE displays ADD COLUMN orientation TEXT NOT NULL DEFAULT '0'")
    if 'override_action' not in cols:
        # Manual on/off/dim control independent of time-based schedules - NULL
        # means "defer to the schedule (if any), otherwise show the layout".
        conn.execute('ALTER TABLE displays ADD COLUMN override_action TEXT')
        conn.execute("ALTER TABLE displays ADD COLUMN override_target TEXT DEFAULT ''")


def init_db():
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()

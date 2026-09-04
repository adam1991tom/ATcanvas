import json
import sqlite3
import sys

in_path, db_path = sys.argv[1], sys.argv[2]
with open(in_path) as f:
    values = json.load(f)

new = sqlite3.connect(db_path)
new.execute("CREATE TABLE IF NOT EXISTS secrets(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
new.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)")

secret_keys = {'google_client_id', 'google_client_secret', 'google_refresh_token'}
setting_keys = {'google_selected_calendars'}

for k in secret_keys:
    if k in values:
        new.execute("INSERT INTO secrets(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, values[k]))
for k in setting_keys:
    if k in values:
        new.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, values[k]))

new.commit()
new.close()
print('Applied to', db_path)

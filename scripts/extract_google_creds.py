import json
import sqlite3
import sys

old_db, out_path = sys.argv[1], sys.argv[2]
old = sqlite3.connect(old_db)
old.row_factory = sqlite3.Row
keys = ['google_client_id', 'google_client_secret', 'google_refresh_token', 'google_selected_calendars']
marks = ','.join('?' for _ in keys)
rows = old.execute(f'SELECT key,value FROM settings WHERE key IN ({marks})', keys).fetchall()
old.close()
values = {r['key']: r['value'] for r in rows}
with open(out_path, 'w') as f:
    json.dump(values, f)
print('Extracted keys:', sorted(values.keys()))

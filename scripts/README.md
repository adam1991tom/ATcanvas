# Google credential migration

Reuses an existing Google Calendar OAuth connection (client ID/secret + refresh
token) instead of making someone redo the interactive consent flow. The
refresh token alone is enough to mint new access tokens - no redirect_uri or
browser round-trip needed.

Usage (adam has read access to the old app's world-readable DB; the target DB
is owned by root inside its container, so apply_google_creds.py must run
*inside* that container, not on the host):

```
python3 extract_google_creds.py /opt/ATcanvas/data/at-canvas.db /tmp/gcreds.json
docker cp apply_google_creds.py <container>:/tmp/apply_google_creds.py
docker cp /tmp/gcreds.json <container>:/tmp/gcreds.json
docker exec <container> python3 /tmp/apply_google_creds.py /tmp/gcreds.json /data/at-canvas.db
docker exec <container> rm -f /tmp/apply_google_creds.py /tmp/gcreds.json
rm -f /tmp/gcreds.json
```

Used once already to bring the existing connection into the staging
environment during the rebuild. Run again at production cutover against
/opt/ATcanvas/data/at-canvas.db (the new app's fresh DB) so the family
calendar doesn't need to be reconnected from scratch.

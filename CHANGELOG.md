# Changelog

## 0.2.1
- Added per-display orientation control
- Added 0°, 90°, 180° and 270° display rotation states
- Added Rotate 90° action to paired display controls
- Added layout rotation between landscape and portrait
- Layout designer canvas now follows the selected layout aspect ratio
- Display heartbeat now returns the desired orientation for the Linux display client

## 0.2.0
- Replaced placeholder admin actions with working controls
- Added persistent layouts stored in SQLite
- Added 16:9 layout designer with draggable and resizable layers
- Added widget layer creation for clock, text, calendar, photos, weather, countdown and media
- Added layer visibility, locking and deletion controls
- Added real media uploads for JPG, PNG, GIF, WebP, MP4 and WebM
- Added event creation and deletion
- Added schedule creation and deletion
- Added persistent system settings
- Added Google OAuth credential configuration screen
- Added GitHub update check

## 0.1.1
- Fixed left sidebar navigation
- Added working Dashboard, Displays, Layouts, Media, Calendars, Events, Schedules, Updates and Settings views
- Added hash-based page state so sections can be refreshed/bookmarked
- Added responsive mobile navigation
- Added live display manager view
- Made application version repository-controlled instead of pinned in .env

## 0.1.0
- Initial GitHub-ready scaffold
- FastAPI server
- Dark admin dashboard
- Six-digit pairing API and pairing page
- Display registration and heartbeat model
- Remote command queue foundations
- Docker Compose deployment
- GitHub Actions build/release workflows

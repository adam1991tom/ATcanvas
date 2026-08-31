# Changelog

## 0.3.0
- Added a guaranteed server-side display test screen at `/display/test`
- Added stable per-display render URLs at `/display/<token>`
- Added per-display Test Screen mode and layout assignment controls
- Display heartbeat now returns the render URL, test mode, layout and active scheduled action
- Added real saved-layout rendering for clock, text, countdown, media and placeholder service widgets
- Added layout property editing for name, text, colour, background, opacity, position, size and z-order
- Rebuilt schedules as reusable schedule profiles containing multiple time blocks
- Added schedule block evaluation including overnight time ranges
- Preserved existing schedule rows by migrating their old time/action data into schedule blocks
- Added a logo fallback so the admin can never show a broken-image icon
- Focused this release on an end-to-end testable working model before Google Calendar and Google Photos integration

## 0.2.4
- Replaced Room selection in the display pairing workflow with Schedule assignment
- Added persistent per-display schedule assignment
- Added schedule selector controls directly to paired display rows
- Display heartbeat now returns assigned schedule ID and name
- Existing databases migrate automatically by adding schedule_id to displays

## 0.2.3
- Fixed AT Canvas logo rendering by embedding the bundled logo directly into the admin and pairing pages
- Added Screen On control for paired displays
- Renamed Off control to Screen Off for clarity
- Added Screen On as a scheduling action

## 0.2.2
- Added the official AT Canvas logo asset
- Rebranded the admin UI with the purple/black AT Canvas colour palette
- Added the official logo to the admin sidebar and browser favicon
- Rebuilt the display pairing page with AT Canvas branding
- Pairing codes are now grouped visually as 3 + 3 digits

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

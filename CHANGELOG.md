# Changelog

## 0.3.4
- Retired the dedicated AT Canvas display client and custom display OS model
- Removed display-client source and systemd service from the active server branch
- Removed six-digit pairing, heartbeat and remote client command routes from the live application
- Replaced paired devices with permanent browser display URLs
- Added Create Display URL workflow in the admin interface
- Added Open Display, Copy URL, Test Screen and Delete URL controls
- Kept per-display layout and schedule assignment without requiring client software
- Added server-side schedule handling directly in the display URL renderer
- Added browser-based screen-off and dim schedule behaviour
- Added automatic display-page refresh so server changes are picked up without a client updater
- Simplified Updates to server-only release status
- Simplified GitHub releases to server package + server Docker image only
- Updated architecture and README for the browser-only display model

## 0.3.3
- Replaced layered legacy admin JavaScript with one clean interface controller
- Stabilized display layout and schedule selectors so saved choices stop flickering/resetting
- Added layout settings editor for name, resolution and background colour
- Added layout preview, duplicate and rotate controls
- Added layer property editing for text, colours, size, opacity, position and media selection
- Added layer duplicate and z-order controls
- Rebuilt schedules in the UI as reusable profiles containing editable time blocks
- Added weekday/weekend/every-day schedule choices
- Added schedule actions for layout, screen on, screen off, dim and normal brightness
- Added event editing instead of create/delete only
- Improved media preview/open/delete workflow
- Added branch-aware update status
- Added Python and JavaScript syntax checks to server CI
- Replaced the unreliable sidebar image with a guaranteed AT Canvas text mark until static branding is rebuilt cleanly

## 0.3.0
- Added a guaranteed server-side display test screen at `/display/test`
- Added stable per-display render URLs at `/display/<token>`
- Added per-display Test Screen mode and layout assignment controls
- Added real saved-layout rendering for clock, text, countdown, media and placeholder service widgets
- Added layout property editing for name, text, colour, background, opacity, position, size and z-order
- Rebuilt schedules as reusable schedule profiles containing multiple time blocks
- Added schedule block evaluation including overnight time ranges
- Preserved existing schedule rows by migrating their old time/action data into schedule blocks
- Added a logo fallback so the admin can never show a broken-image icon

## 0.2.4
- Replaced Room selection in the display pairing workflow with Schedule assignment
- Added persistent per-display schedule assignment
- Added schedule selector controls directly to paired display rows
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

# Changelog

## 0.6.1
- Fixed the admin page's version badge being permanently frozen at "v0.4.0" - v40.py
  had a one-time hardcoded `.replace('v0.3.5','v0.4.0')` from an old release that
  was never updated by any later version file, so the visible badge never matched
  what was actually deployed. Now reads the live version at request time.
- Added `Cache-Control: no-store` to the admin page and JS bundle so a browser (or
  proxy) can never serve a stale cached copy after a deploy

## 0.6.0
- The layout designer now shows a live, true-to-scale preview behind the draggable
  widget boxes, rendered from the same pipeline the real display uses (not a
  redrawn approximation) - what you see while editing is what actually shows on
  the wall

## 0.5.0
- Added a native To-Do / chores list: shared checklist stored on the server, managed
  from a new admin To-Do page, and a `todo` widget layer that can be added to any
  layout - items can be ticked directly on the wall display itself (no login needed
  on that one action, matching the "anyone standing at the screen" trust model of a
  kiosk display)
- Added seasonal/holiday display effects: each Event can now be given an effect
  (snow, rain, halloween, confetti, hearts, stars) that automatically renders as a
  fullscreen animated overlay on every display while that event's date range is active
- Added an optional fullscreen weather animation: when enabled on a weather widget,
  the display renders a fullscreen animated overlay (rain/snow/fog/stars/etc.) driven
  by the widget's live weather condition when no seasonal event is active
- Investigated Google Photos as a photo-widget source: Google discontinued
  third-party live album access in March 2025 (shared albums and broad Library API
  access now return 403), so a DAKboard-style syncing photo album isn't currently
  buildable - the existing local-upload photo slideshow widget remains the supported
  path

## 0.4.1
- Fixed reflected XSS in the Google OAuth callback error page (error text is now HTML-escaped)
- Added admin login (username/password, signed session cookie) in front of the admin UI and all `/api/*` routes
- Kept `/display/<token>` pages, display media/widget data endpoints and `/api/health` publicly reachable so existing screens keep working without logging in
- Admin password and username are now set via `AT_CANVAS_ADMIN_USER` / `AT_CANVAS_ADMIN_PASSWORD` in `.env`

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

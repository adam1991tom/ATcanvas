# Architecture

## Principles
1. Server owns configuration, integrations and layouts.
2. Displays are thin Linux kiosk clients.
3. Displays pair using a short-lived six-digit code.
4. Long-lived device credentials replace pairing codes after claim.
5. Layouts use a layer model so event/season overlays can be scheduled independently.
6. Remote commands include identify, reload, power/display state, reboot and client update.
7. Google credentials remain server-side.

## Planned modules
- Displays
- Layouts + Layers
- Google Calendar
- Google Photos / media library
- Events / seasonal overlays
- Schedules / night mode / brightness
- Server updater
- Display OTA updater

# Architecture

## Principles
1. The AT Canvas server owns configuration, integrations, layouts, schedules and rendering.
2. Displays are permanent browser URLs served directly by AT Canvas.
3. No dedicated display client, pairing agent, heartbeat service or custom display OS is required.
4. Any modern browser-capable device can show an AT Canvas display URL fullscreen.
5. Layouts use a layer model so widgets and seasonal/event overlays can be arranged independently.
6. Schedules are evaluated server-side and can switch layouts, show a black screen or apply a dim overlay.
7. Display pages refresh automatically so server changes are picked up without client software updates.
8. Google credentials remain server-side.

## Core modules
- Display URLs
- Layouts + Layers
- Media library
- Google Calendar
- Google Photos
- Events / seasonal overlays
- Schedules / night mode
- Server updater

# AT Canvas

AT Canvas is a self-hosted smart display platform. The server hosts the admin interface, layouts, schedules, media and the final display pages.

## Display model
There is no dedicated display client or custom display OS.

Create a Display URL in the AT Canvas admin interface, then open that permanent URL fullscreen in any modern browser-capable device.

Example:
```text
http://at-canvas-server:8077/display/<endpoint-token>
```

A display URL can be assigned a layout and schedule from the server. The page automatically refreshes so layout and schedule changes are picked up without installing AT Canvas software on the display device.

## Quick start
```bash
cp .env.example .env
docker compose up --build -d
```

Admin: `http://localhost:8077`

API docs: `http://localhost:8077/docs`

# Browser-only display migration

AT Canvas v0.3.4 retires the dedicated display client model.

Existing display records are preserved and their tokens become permanent browser display endpoint IDs. Pairing codes, heartbeats and remote client commands are no longer used.

To use a display, open its `/display/<token>` URL fullscreen in any modern browser. Layout and schedule changes are evaluated by the server and the display page refreshes automatically.

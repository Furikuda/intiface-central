# Client Mode server

The remote endpoint for Intiface Central's **Client Mode**, plus a browser bridge
so a second person can drive the toy.

Two listeners:

- **`:8765` WebSocket** — the app dials in here. We act as the Buttplug *client*.
- **`:80` HTTP** (plain, no TLS) — a browser enters a name + session ID and gets a
  control page.

## How it works

1. The app (Client Mode) generates a **session ID** (a 4-word passphrase), shows it,
   and advertises it as its Buttplug *server name*.
2. The app connects to `:8765`; we hold it **pending** (no Buttplug handshake yet).
3. Someone opens `http://<server>/`, enters **their name + the session ID**.
4. We handshake the app with `ClientName = <their name>` and check the app's server
   name equals the typed session ID. On match: the app shows **"<name> connected"**,
   we scan/track devices, and the browser is sent to the control page.
5. Sliders on the control page send `ScalarCmd`s to the app, which drives the toy.

### Known limitations (by design)

A Buttplug connection allows exactly one handshake and the app's engine stops if the
connection drops (no auto-reconnect). So:

- **One controller per app session.**
- A **wrong/typo'd session ID consumes the handshake** — the app must restart Client
  Mode. (The form is rate limited to blunt guessing.)

No TLS, no real auth — **test-only**.

## Setup

```bash
cd server
pip install -r requirements.txt
```

## Run

Port 80 needs privilege. For local dev use a high port:

```bash
WEB_PORT=8080 python3 server.py
```

For real port 80: `sudo python3 server.py` (or grant the binary `cap_net_bind_service`).

```
[12:00:00] server: App WebSocket on ws://0.0.0.0:8765 | Web UI on http://0.0.0.0:80
```

Point the app's Client Mode at `ws://<server-ip>:8765`, then share the session ID it
shows and have your friend open `http://<server-ip>/` (or `:8080` in dev).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Unit tests live in `tests/` and cover the protocol builders, session registry,
the Buttplug bridge (handshake/verify, command relay, disconnect handling), and
the web routes/control websocket.

## Files

- `server.py` — entrypoint, starts both listeners.
- `buttplug_bridge.py` — app-facing Buttplug client (deferred handshake, device relay).
- `buttplug_protocol.py` — minimal Buttplug v3 message builders.
- `sessions.py` — in-memory session registry.
- `web.py` — aiohttp routes + control websocket.
- `templates/` — the form and control pages.

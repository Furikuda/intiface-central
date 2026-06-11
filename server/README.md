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

Point the app's Client Mode at the server URL (see below), then share the link the app
shows ("copy control link") with your friend.

## Reverse proxy / base path (recommended)

The app's Client Mode takes a single **Server URL** like `https://domain.com/intiface`
and derives both endpoints from it:

- engine websocket → `wss://domain.com/intiface/ws`
- control link → `https://domain.com/intiface/?session=<id>` (opens the form prefilled)

So put both listeners behind one host:port, split by path. The browser control socket
lives at `<base>/socket/<id>` (deliberately **not** under `/ws`) so the proxy can route
`<base>/ws` to the app websocket without catching it. Example nginx:

```nginx
location = /intiface/ws {                 # app (engine) websocket -> :8765
  proxy_pass http://127.0.0.1:8765/;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
}
location /intiface/ {                      # web UI + control socket -> :80
  proxy_pass http://127.0.0.1:80/;         # trailing slash strips the base path
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;   # control socket at /intiface/socket/<id>
  proxy_set_header Connection "upgrade";
}
```

Because the app derives both endpoints from one host:port, the two listeners must share
one — so even local testing wants a tiny proxy. A minimal Caddyfile (root base path):

```
:8443 {
  handle /ws        { reverse_proxy 127.0.0.1:8765 }   # app websocket
  handle            { reverse_proxy 127.0.0.1:8080 }   # web UI + /socket/<id>
}
```

Then set the app's Server URL to `http://localhost:8443` (engine → `ws://localhost:8443/ws`,
link → `http://localhost:8443/?session=<id>`).

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

# Client Mode test server

A tiny WebSocket server skeleton that the Intiface Central app connects to when
running in **Client Mode**. It listens on port `8765`, accepts connections, and
prints the content of every received message to the console.

This is boilerplate only — it does not yet send any commands back.

## Setup

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
```

## Run

```bash
python3 server.py
```

You should see:

```
[12:00:00] WebSocket server listening on ws://0.0.0.0:8765
```

Point the app's Client Mode at `ws://<this-machine-ip>:8765` and incoming
messages will be printed to the console.

"""Minimal WebSocket server boilerplate for Intiface Central "Client Mode".

Listens on port 8765 and prints the content of everything it receives to the
console. This is intentionally a skeleton: it does not yet send any Buttplug
commands back — that's for a later iteration.

Run:
    pip install -r requirements.txt
    python3 server.py
"""

import asyncio
from datetime import datetime

from websockets.asyncio.server import serve

HOST = "0.0.0.0"
PORT = 8765


def _log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


async def handler(websocket) -> None:
    """Handle a single client connection: print every message it sends."""
    peer = websocket.remote_address  # (host, port) of the connected client
    _log(f"Client connected: {peer}")
    try:
        async for message in websocket:
            _log(f"Received from {peer}: {message!r}")
    finally:
        _log(f"Client disconnected: {peer}")


async def main() -> None:
    async with serve(handler, HOST, PORT):
        _log(f"WebSocket server listening on ws://{HOST}:{PORT}")
        await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")

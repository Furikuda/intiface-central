"""Two-port server for Intiface Central "Client Mode".

  * Port 8765 (WebSocket): the app dials in here. We drive it as a Buttplug client.
  * Port 80 (plain HTTP):  a browser enters their name + the app's session ID and
                           gets a page to control the toy.

Override ports with env vars for local dev without root:
    WS_PORT=8765 WEB_PORT=8080 python3 server.py

Run:
    pip install -r requirements.txt
    python3 server.py
"""

import asyncio
import logging
import os

from aiohttp import web
from websockets.asyncio.server import serve

from buttplug_bridge import handle_app
from sessions import SessionManager
from web import make_web_app

HOST = "0.0.0.0"
WS_PORT = int(os.environ.get("WS_PORT", "8765"))
WEB_PORT = int(os.environ.get("WEB_PORT", "80"))


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    manager = SessionManager()

    # App-facing WebSocket listener.
    ws_server = await serve(lambda ws: handle_app(ws, manager), HOST, WS_PORT)

    # Browser-facing HTTP listener.
    runner = web.AppRunner(make_web_app(manager))
    await runner.setup()
    site = web.TCPSite(runner, HOST, WEB_PORT)
    await site.start()

    logging.getLogger("server").info(
        "App WebSocket on ws://%s:%s | Web UI on http://%s:%s", HOST, WS_PORT, HOST, WEB_PORT
    )
    try:
        await asyncio.get_running_loop().create_future()  # run forever
    finally:
        ws_server.close()
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")

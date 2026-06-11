"""Browser-facing side (port 80, plain HTTP).

Flow:
  GET  /                 -> form: your name + the session ID
  POST /                 -> verify by activating the pending app connection;
                            on success redirect to /control/<session_id>
  GET  /control/<sid>    -> control page (sliders/stop per actuator)
  GET  /ws/control/<sid> -> control websocket carrying live commands

No TLS, minimal auth: knowing the session ID is the only gate, so the POST form
is rate limited per IP. Test-only.
"""

import logging
import time
from pathlib import Path

from aiohttp import web

log = logging.getLogger("web")

_TEMPLATES = Path(__file__).parent / "templates"

# crude per-IP rate limit on the entry form
_RATE_MAX = 5            # attempts
_RATE_WINDOW = 30.0      # seconds
_attempts: dict[str, list[float]] = {}


def _render(name: str, **subs: str) -> str:
    html = (_TEMPLATES / name).read_text(encoding="utf-8")
    for key, value in subs.items():
        html = html.replace("{{" + key + "}}", value)
    return html


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _attempts.get(ip, []) if now - t < _RATE_WINDOW]
    hits.append(now)
    _attempts[ip] = hits
    return len(hits) > _RATE_MAX


async def index(request: web.Request) -> web.Response:
    return web.Response(text=_render("index.html", ERROR=""), content_type="text/html")


async def submit(request: web.Request) -> web.Response:
    ip = request.remote or "?"
    if _rate_limited(ip):
        return web.Response(
            text=_render("index.html", ERROR="Too many attempts. Please wait a moment."),
            content_type="text/html",
            status=429,
        )

    data = await request.post()
    name = (data.get("name") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    if not name or not session_id:
        return web.Response(
            text=_render("index.html", ERROR="Please enter both a name and a session ID."),
            content_type="text/html",
        )

    manager = request.app["manager"]
    conn = manager.take_pending()
    if conn is None:
        return web.Response(
            text=_render("index.html", ERROR="No device is waiting to be connected right now."),
            content_type="text/html",
        )

    ok = await conn.activate(name, session_id)
    if not ok:
        return web.Response(
            text=_render("index.html", ERROR="Invalid session ID."),
            content_type="text/html",
        )

    manager.mark_active(conn)
    raise web.HTTPFound(f"/control/{session_id}")


async def control(request: web.Request) -> web.Response:
    session_id = request.match_info["sid"]
    if request.app["manager"].get_active(session_id) is None:
        raise web.HTTPFound("/")
    return web.Response(
        text=_render("control.html", SESSION_ID=session_id),
        content_type="text/html",
    )


async def control_ws(request: web.Request) -> web.WebSocketResponse:
    session_id = request.match_info["sid"]
    conn = request.app["manager"].get_active(session_id)
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    if conn is None:
        await ws.send_json({"type": "error", "message": "Session not found"})
        await ws.close()
        return ws

    conn.controller_ws = ws
    await ws.send_json({"type": "devices", "devices": conn.devices_payload()})

    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue
            try:
                cmd = msg.json()
            except ValueError:
                continue
            device = int(cmd.get("device"))
            actuator = int(cmd.get("actuator", 0))
            if cmd.get("stop"):
                await conn.stop_device(device)
            else:
                await conn.set_scalar(device, actuator, float(cmd.get("intensity", 0.0)))
    finally:
        if conn.controller_ws is ws:
            conn.controller_ws = None
            # Safety: stop everything when the controller leaves.
            for index in list(conn.devices):
                await conn.stop_device(index)

    return ws


def make_web_app(manager) -> web.Application:
    app = web.Application()
    app["manager"] = manager
    app.add_routes(
        [
            web.get("/", index),
            web.post("/", submit),
            web.get("/control/{sid}", control),
            web.get("/ws/control/{sid}", control_ws),
        ]
    )
    return app

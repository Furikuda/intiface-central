import asyncio

import web
from web import make_web_app


class FakeConn:
    def __init__(self, session_id, *, activate_result=True):
        self.session_id = None
        self._sid = session_id
        self._activate_result = activate_result
        self.activated_with = None
        self.controller_ws = None
        self.scalars = []
        self.stops = []
        self.devices = {0: {"name": "Vibe"}}  # for the safety-stop loop on close

    async def activate(self, name, claimed_session_id):
        self.activated_with = (name, claimed_session_id)
        if self._activate_result:
            self.session_id = self._sid
        return self._activate_result

    def devices_payload(self):
        return [{"index": 0, "name": "Vibe", "actuators": [
            {"index": 0, "type": "Vibrate", "descriptor": "", "steps": 10}]}]

    def stats(self):
        return {
            "session_id": self._sid, "controller_name": "Bob", "duration_seconds": 0,
            "commands": len(self.scalars) + len(self.stops), "devices": 1,
            "current_intensity": 0.0, "peak_intensity": 0.0, "active_seconds": 0,
            "vibration_units": 0.0, "commands_per_minute": 0.0,
        }

    async def set_scalar(self, device, actuator, intensity):
        self.scalars.append((device, actuator, intensity))

    async def stop_device(self, device):
        self.stops.append(device)


class FakeManager:
    def __init__(self):
        self.pending = []
        self.active = {}

    def take_pending(self):
        return self.pending.pop(0) if self.pending else None

    def mark_active(self, conn):
        self.active[conn.session_id] = conn

    def get_active(self, sid):
        return self.active.get(sid)


async def test_index_renders_form(aiohttp_client):
    client = await aiohttp_client(make_web_app(FakeManager()))
    resp = await client.get("/")
    assert resp.status == 200
    text = await resp.text()
    assert "Session ID" in text and 'name="session_id"' in text and 'name="name"' in text


async def test_index_supports_session_prefill(aiohttp_client):
    # The shared link arrives as /?session=word-word; the page prefills it via JS.
    client = await aiohttp_client(make_web_app(FakeManager()))
    resp = await client.get("/?session=amber-otter-lunar-pebble")
    assert resp.status == 200
    text = await resp.text()
    assert "URLSearchParams" in text and 'get("session")' in text


async def test_submit_success_redirects_and_activates(aiohttp_client):
    mgr = FakeManager()
    conn = FakeConn("word-id")
    mgr.pending.append(conn)
    client = await aiohttp_client(make_web_app(mgr))

    resp = await client.post(
        "/", data={"name": "Bob", "session_id": "word-id"}, allow_redirects=False
    )
    assert resp.status == 302
    assert resp.headers["Location"] == "control/word-id"  # relative for base-path support
    assert conn.activated_with == ("Bob", "word-id")
    assert mgr.get_active("word-id") is conn


async def test_submit_missing_fields(aiohttp_client):
    client = await aiohttp_client(make_web_app(FakeManager()))
    resp = await client.post("/", data={"name": "", "session_id": ""})
    assert resp.status == 200
    assert "enter both" in (await resp.text())


async def test_submit_no_pending_device(aiohttp_client):
    client = await aiohttp_client(make_web_app(FakeManager()))
    resp = await client.post("/", data={"name": "Bob", "session_id": "x"})
    assert resp.status == 200
    assert "No device is waiting" in (await resp.text())


async def test_submit_invalid_session_id(aiohttp_client):
    mgr = FakeManager()
    mgr.pending.append(FakeConn("real", activate_result=False))
    client = await aiohttp_client(make_web_app(mgr))

    resp = await client.post(
        "/", data={"name": "Mallory", "session_id": "guess"}, allow_redirects=False
    )
    assert resp.status == 200
    assert "Invalid session ID" in (await resp.text())
    assert mgr.get_active("guess") is None


async def test_submit_is_rate_limited(aiohttp_client):
    client = await aiohttp_client(make_web_app(FakeManager()))
    statuses = []
    for _ in range(web._RATE_MAX + 1):
        resp = await client.post("/", data={"name": "n", "session_id": "s"})
        statuses.append(resp.status)
    # The first _RATE_MAX are allowed (200), the next is blocked.
    assert statuses[-1] == 429
    assert statuses[:-1].count(429) == 0


async def test_control_page_active(aiohttp_client):
    mgr = FakeManager()
    conn = FakeConn("sid1")
    conn.session_id = "sid1"
    mgr.active["sid1"] = conn
    client = await aiohttp_client(make_web_app(mgr))

    resp = await client.get("/control/sid1")
    assert resp.status == 200
    assert "Totally Not Secure Intiface Proxy" in (await resp.text())


async def test_control_page_unknown_redirects_home(aiohttp_client):
    client = await aiohttp_client(make_web_app(FakeManager()))
    resp = await client.get("/control/nope", allow_redirects=False)
    assert resp.status == 302
    assert resp.headers["Location"] == "/"


async def test_control_ws_relays_commands(aiohttp_client):
    mgr = FakeManager()
    conn = FakeConn("sid1")
    conn.session_id = "sid1"
    mgr.active["sid1"] = conn
    client = await aiohttp_client(make_web_app(mgr))

    ws = await client.ws_connect("/socket/sid1")
    first = await ws.receive_json()
    assert first["type"] == "devices"
    # The control page is fed a live stats snapshot right after the device list.
    stats_msg = await ws.receive_json()
    assert stats_msg["type"] == "stats"
    assert stats_msg["stats"]["controller_name"] == "Bob"

    await ws.send_json({"device": 0, "actuator": 0, "intensity": 0.5})
    await ws.send_json({"device": 0, "stop": True})
    await asyncio.sleep(0.05)
    await ws.close()

    assert (0, 0, 0.5) in conn.scalars
    assert 0 in conn.stops


async def test_control_ws_stop_all(aiohttp_client):
    mgr = FakeManager()
    conn = FakeConn("sid1")
    conn.session_id = "sid1"
    conn.devices = {0: {"name": "A"}, 1: {"name": "B"}}
    mgr.active["sid1"] = conn
    client = await aiohttp_client(make_web_app(mgr))

    ws = await client.ws_connect("/socket/sid1")
    await ws.receive_json()  # devices
    await ws.receive_json()  # stats
    await ws.send_json({"stop_all": True})
    await asyncio.sleep(0.05)
    # Assert before closing: the close-time safety-stop would also stop everything,
    # so checking here proves stop_all itself did the work.
    assert sorted(conn.stops) == [0, 1]
    await ws.close()


async def test_control_ws_unknown_session(aiohttp_client):
    client = await aiohttp_client(make_web_app(FakeManager()))
    ws = await client.ws_connect("/socket/nope")
    msg = await ws.receive_json()
    assert msg["type"] == "error"
    await ws.close()

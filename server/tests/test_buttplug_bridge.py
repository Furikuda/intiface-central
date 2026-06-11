import asyncio
import json

import pytest
from websockets.exceptions import ConnectionClosed

from buttplug_bridge import ButtplugAppConnection, ButtplugError
from sessions import SessionManager

VIBE_DEVICE = {
    "DeviceName": "Test Vibe",
    "DeviceIndex": 0,
    "DeviceMessages": {
        "ScalarCmd": [
            {"StepCount": 20, "ActuatorType": "Vibrate", "FeatureDescriptor": "Vibrator"}
        ]
    },
}


class FakeAppWebSocket:
    """Stands in for the app (the Buttplug server) on the bridge's app_ws.

    Auto-responds to requests like a real server would, so the bridge's read loop
    can resolve its request futures.
    """

    def __init__(self, *, server_name="word-word", max_ping_time=0, devices=None,
                 auto=True, raise_on_send=None):
        self.sent = []                 # list of single-message dicts the bridge sent
        self.server_name = server_name
        self.max_ping_time = max_ping_time
        self.devices = devices if devices is not None else []
        self.auto = auto
        self.raise_on_send = raise_on_send
        self._incoming: asyncio.Queue = asyncio.Queue()

    async def send(self, data):
        if self.raise_on_send is not None:
            raise self.raise_on_send
        for message in json.loads(data):
            self.sent.append(message)
            if self.auto:
                self._auto_respond(message)

    def _auto_respond(self, message):
        for mtype, body in message.items():
            mid = body.get("Id", 0)
            if mtype == "RequestServerInfo":
                self._push({"ServerInfo": {
                    "Id": mid, "ServerName": self.server_name,
                    "MessageVersion": 3, "MaxPingTime": self.max_ping_time}})
            elif mtype == "RequestDeviceList":
                self._push({"DeviceList": {"Id": mid, "Devices": self.devices}})
            else:
                self._push({"Ok": {"Id": mid}})

    def _push(self, message):
        self._incoming.put_nowait(json.dumps([message]))

    def push_raw(self, message):
        """Inject an unsolicited event (e.g. DeviceAdded) into the read loop."""
        self._incoming.put_nowait(json.dumps([message]))

    async def close(self):
        self._incoming.put_nowait(None)  # sentinel ends the read loop

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self._incoming.get()
        if item is None:
            raise StopAsyncIteration
        return item

    def sent_of_type(self, msg_type):
        return [m[msg_type] for m in self.sent if msg_type in m]


async def _run(conn):
    task = asyncio.create_task(conn.run())
    await asyncio.sleep(0)  # let the read loop start
    return task


async def test_activate_success_loads_devices_and_scans():
    ws = FakeAppWebSocket(server_name="alpha-beta", devices=[VIBE_DEVICE])
    conn = ButtplugAppConnection(ws, SessionManager())
    task = await _run(conn)

    ok = await conn.activate("Bob", "alpha-beta")

    assert ok is True
    assert conn.active is True
    assert conn.session_id == "alpha-beta"
    assert conn.devices[0]["name"] == "Test Vibe"
    assert conn.devices[0]["actuators"][0]["type"] == "Vibrate"
    # Handshake carried the browser user's name.
    assert ws.sent_of_type("RequestServerInfo")[0]["ClientName"] == "Bob"
    # And we started scanning.
    assert ws.sent_of_type("StartScanning")

    await ws.close()
    await asyncio.wait_for(task, 1)


async def test_activate_rejects_session_id_mismatch():
    ws = FakeAppWebSocket(server_name="real-id", devices=[VIBE_DEVICE])
    conn = ButtplugAppConnection(ws, SessionManager())
    task = await _run(conn)

    ok = await conn.activate("Mallory", "wrong-id")

    assert ok is False
    assert conn.active is False
    assert conn.session_id is None
    # We never asked for the device list on a mismatch.
    assert not ws.sent_of_type("RequestDeviceList")

    await ws.close()
    await asyncio.wait_for(task, 1)


async def test_activate_is_one_shot():
    ws = FakeAppWebSocket(server_name="alpha-beta", devices=[VIBE_DEVICE])
    conn = ButtplugAppConnection(ws, SessionManager())
    task = await _run(conn)

    assert await conn.activate("Bob", "alpha-beta") is True
    # The single handshake is spent; a second attempt cannot re-handshake.
    assert await conn.activate("Eve", "alpha-beta") is False

    await ws.close()
    await asyncio.wait_for(task, 1)


async def test_set_scalar_sends_clamped_scalarcmd():
    ws = FakeAppWebSocket(server_name="sid", devices=[VIBE_DEVICE])
    conn = ButtplugAppConnection(ws, SessionManager())
    task = await _run(conn)
    await conn.activate("Bob", "sid")

    await conn.set_scalar(0, 0, 0.5)
    await conn.set_scalar(0, 0, 5.0)    # clamps to 1.0
    await conn.set_scalar(0, 0, -1.0)   # clamps to 0.0

    cmds = ws.sent_of_type("ScalarCmd")
    assert cmds[0]["Scalars"][0] == {"Index": 0, "Scalar": 0.5, "ActuatorType": "Vibrate"}
    assert cmds[1]["Scalars"][0]["Scalar"] == 1.0
    assert cmds[2]["Scalars"][0]["Scalar"] == 0.0

    await ws.close()
    await asyncio.wait_for(task, 1)


async def test_set_scalar_ignores_unknown_device_and_actuator():
    ws = FakeAppWebSocket(server_name="sid", devices=[VIBE_DEVICE])
    conn = ButtplugAppConnection(ws, SessionManager())
    task = await _run(conn)
    await conn.activate("Bob", "sid")

    await conn.set_scalar(99, 0, 0.5)   # no such device
    await conn.set_scalar(0, 99, 0.5)   # no such actuator
    assert ws.sent_of_type("ScalarCmd") == []

    await ws.close()
    await asyncio.wait_for(task, 1)


async def test_stop_device_sends_stop_device_cmd():
    ws = FakeAppWebSocket(server_name="sid", devices=[VIBE_DEVICE])
    conn = ButtplugAppConnection(ws, SessionManager())
    task = await _run(conn)
    await conn.activate("Bob", "sid")

    await conn.stop_device(0)
    assert ws.sent_of_type("StopDeviceCmd")[0]["DeviceIndex"] == 0

    await ws.close()
    await asyncio.wait_for(task, 1)


async def test_send_swallows_connection_closed():
    # Regression: safety-stop after the app is gone must not raise.
    ws = FakeAppWebSocket(raise_on_send=ConnectionClosed(None, None))
    conn = ButtplugAppConnection(ws, SessionManager())
    await conn.stop_device(0)  # should not raise


async def test_dispatch_device_added_and_removed_notify_controller():
    ws = FakeAppWebSocket()
    conn = ButtplugAppConnection(ws, SessionManager())

    sent_to_controller = []

    class FakeControllerWS:
        async def send_json(self, payload):
            sent_to_controller.append(payload)

    conn.controller_ws = FakeControllerWS()

    conn._dispatch("DeviceAdded", VIBE_DEVICE)
    await asyncio.sleep(0)  # let the create_task'd send_json run
    assert 0 in conn.devices
    assert sent_to_controller[-1]["type"] == "devices"
    assert sent_to_controller[-1]["devices"][0]["index"] == 0

    conn._dispatch("DeviceRemoved", {"DeviceIndex": 0})
    await asyncio.sleep(0)
    assert 0 not in conn.devices
    assert sent_to_controller[-1]["devices"] == []


async def test_dispatch_error_fails_the_pending_request():
    ws = FakeAppWebSocket()
    conn = ButtplugAppConnection(ws, SessionManager())
    fut = asyncio.get_running_loop().create_future()
    conn._pending[42] = fut

    conn._dispatch("Error", {"Id": 42, "ErrorMessage": "boom"})

    with pytest.raises(ButtplugError):
        await fut


def test_devices_payload_shape():
    ws = FakeAppWebSocket()
    conn = ButtplugAppConnection(ws, SessionManager())
    conn._add_device(VIBE_DEVICE)
    payload = conn.devices_payload()
    assert payload == [
        {
            "index": 0,
            "name": "Test Vibe",
            "actuators": [
                {"index": 0, "type": "Vibrate", "descriptor": "Vibrator", "steps": 20}
            ],
        }
    ]

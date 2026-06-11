"""App-facing side: a minimal Buttplug *client* over one app connection.

In Client Mode the app is the Buttplug *server* and dials out to us, so we drive
it as the client. We deliberately **defer the handshake** until a browser submits
the form: the handshake's ``ClientName`` becomes the browser user's name (which
the app then shows as "<name> connected"), and the ``ServerInfo.ServerName`` we
get back is the session ID the app advertised — which we check against what the
browser typed.

Note the inherent limit of this single-connection design: a Buttplug transport
allows exactly one handshake, so a wrong/typo'd session ID consumes it and the
session is spent (the app must restart Client Mode).
"""

import asyncio
import json
import logging
import time

from websockets.exceptions import ConnectionClosed

import buttplug_protocol as proto

log = logging.getLogger("bridge")

_REQUEST_TIMEOUT = 10.0


class ButtplugError(Exception):
    def __init__(self, body: dict) -> None:
        super().__init__(body.get("ErrorMessage", "Buttplug error"))
        self.body = body


class ButtplugAppConnection:
    def __init__(self, app_ws, manager) -> None:
        self.app_ws = app_ws
        self.manager = manager
        self.session_id: str | None = None
        self.active = False
        self.devices: dict[int, dict] = {}      # index -> {"name", "actuators":[...]}
        self.controller_ws = None               # attached browser control websocket

        self._handshaken = False
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._send_lock = asyncio.Lock()
        self._ping_task: asyncio.Task | None = None
        self.max_ping_time = 0

        # Live session stats (surfaced to the control page).
        self.controller_name: str | None = None
        self.activated_at: float | None = None
        self.command_count = 0
        self.peak_intensity = 0.0
        self.active_seconds = 0.0
        self.vibration_units = 0.0                  # ∫ intensity dt — a fun cumulative score
        self._intensities: dict[tuple[int, int], float] = {}
        self._stats_task: asyncio.Task | None = None

    # ---- lifecycle ---------------------------------------------------------

    async def run(self) -> None:
        """Read loop; runs until the app disconnects."""
        try:
            async for raw in self.app_ws:
                try:
                    batch = json.loads(raw)
                except json.JSONDecodeError:
                    log.warning("Bad JSON from app: %r", raw)
                    continue
                for message in batch:
                    for msg_type, body in message.items():
                        self._dispatch(msg_type, body)
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        if self._ping_task:
            self._ping_task.cancel()
        if self._stats_task:
            self._stats_task.cancel()
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
        self.manager.remove(self)
        if self.controller_ws is not None:
            asyncio.create_task(self.controller_ws.close())

    # ---- activation (triggered by the web form) ----------------------------

    async def activate(self, name: str, claimed_session_id: str) -> bool:
        """Handshake with ClientName=name; verify the typed session ID.

        Returns True only if the app's advertised ServerName matches. Either way
        the single handshake is now spent.
        """
        if self._handshaken:
            return False
        self._handshaken = True

        info = await self._request(proto.request_server_info(self._next_id(), name))
        server_name = info.get("ServerName", "")
        self.max_ping_time = info.get("MaxPingTime", 0) or 0

        if server_name != claimed_session_id:
            log.info("Session ID mismatch (got %r, typed %r)", server_name, claimed_session_id)
            return False

        self.session_id = server_name
        if self.max_ping_time > 0:
            self._ping_task = asyncio.create_task(self._ping_loop())

        device_list = await self._request(proto.request_device_list(self._next_id()))
        for device in device_list.get("Devices", []):
            self._add_device(device)
        await self._send(proto.start_scanning(self._next_id()))

        self.active = True
        self.controller_name = name
        self.activated_at = time.monotonic()
        self._stats_task = asyncio.create_task(self._sample_stats())
        log.info("Session %s activated by %r", self.session_id, name)
        return True

    # ---- control (triggered by the browser) --------------------------------

    async def set_scalar(self, device_index: int, actuator_index: int, intensity: float) -> None:
        device = self.devices.get(device_index)
        if not device:
            return
        actuator = next(
            (a for a in device["actuators"] if a["index"] == actuator_index), None
        )
        if not actuator:
            return
        intensity = max(0.0, min(1.0, float(intensity)))
        await self._send(
            proto.scalar_cmd(
                self._next_id(),
                device_index,
                [{"Index": actuator_index, "Scalar": intensity, "ActuatorType": actuator["type"]}],
            )
        )
        self._intensities[(device_index, actuator_index)] = intensity
        self.peak_intensity = max(self.peak_intensity, intensity)
        self.command_count += 1

    async def stop_device(self, device_index: int) -> None:
        await self._send(proto.stop_device_cmd(self._next_id(), device_index))
        for key in list(self._intensities):
            if key[0] == device_index:
                self._intensities[key] = 0.0
        self.command_count += 1

    def devices_payload(self) -> list[dict]:
        return [
            {"index": idx, "name": d["name"], "actuators": d["actuators"]}
            for idx, d in sorted(self.devices.items())
        ]

    def _current_intensity(self) -> float:
        return max(self._intensities.values(), default=0.0)

    def stats(self) -> dict:
        """A snapshot of fun/interesting session numbers for the control page."""
        duration = (time.monotonic() - self.activated_at) if self.activated_at else 0.0
        minutes = duration / 60.0
        return {
            "session_id": self.session_id,
            "controller_name": self.controller_name,
            "duration_seconds": int(duration),
            "commands": self.command_count,
            "devices": len(self.devices),
            "current_intensity": round(self._current_intensity(), 3),
            "peak_intensity": round(self.peak_intensity, 3),
            "active_seconds": int(self.active_seconds),
            "vibration_units": round(self.vibration_units, 1),
            "commands_per_minute": round(self.command_count / minutes, 1) if minutes > 0 else 0.0,
        }

    async def _sample_stats(self) -> None:
        """Accumulate time-integrated stats (active time, vibration units)."""
        interval = 0.5
        try:
            while True:
                await asyncio.sleep(interval)
                current = self._current_intensity()
                if current > 0:
                    self.active_seconds += interval
                self.vibration_units += current * interval
        except asyncio.CancelledError:
            pass

    # ---- internals ---------------------------------------------------------

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    async def _send(self, message: dict) -> None:
        data = json.dumps([message])
        async with self._send_lock:
            try:
                await self.app_ws.send(data)
            except ConnectionClosed:
                # The app disconnected; nothing to send to. This is expected, e.g. when
                # the controller's safety-stop fires after the app has already gone away.
                log.debug("App connection closed; dropping outgoing message")

    async def _request(self, message: dict) -> dict:
        msg_id = next(iter(message.values()))["Id"]
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut
        await self._send(message)
        return await asyncio.wait_for(fut, _REQUEST_TIMEOUT)

    def _dispatch(self, msg_type: str, body: dict) -> None:
        msg_id = body.get("Id", 0)
        fut = self._pending.pop(msg_id, None) if msg_id else None

        if msg_type == "Error":
            if fut and not fut.done():
                fut.set_exception(ButtplugError(body))
            else:
                log.warning("Buttplug error: %s", body.get("ErrorMessage"))
            return

        if fut and not fut.done():
            fut.set_result(body)
            return

        # Unsolicited events.
        if msg_type == "DeviceAdded":
            self._add_device(body)
            self._notify_controller_devices()
        elif msg_type == "DeviceRemoved":
            self.devices.pop(body.get("DeviceIndex"), None)
            self._notify_controller_devices()

    def _add_device(self, device: dict) -> None:
        index = device["DeviceIndex"]
        scalars = device.get("DeviceMessages", {}).get("ScalarCmd", [])
        actuators = [
            {
                "index": i,
                "type": s.get("ActuatorType", "Vibrate"),
                "descriptor": s.get("FeatureDescriptor", ""),
                "steps": s.get("StepCount", 0),
            }
            for i, s in enumerate(scalars)
        ]
        self.devices[index] = {"name": device.get("DeviceName", f"Device {index}"), "actuators": actuators}

    def _notify_controller_devices(self) -> None:
        if self.controller_ws is not None:
            payload = {"type": "devices", "devices": self.devices_payload()}
            asyncio.create_task(self.controller_ws.send_json(payload))

    async def _ping_loop(self) -> None:
        interval = max(0.5, self.max_ping_time / 1000.0 / 2.0)
        try:
            while True:
                await asyncio.sleep(interval)
                await self._send(proto.ping(self._next_id()))
        except asyncio.CancelledError:
            pass


async def handle_app(app_ws, manager) -> None:
    """websockets handler for each inbound app connection."""
    conn = ButtplugAppConnection(app_ws, manager)
    manager.add_pending(conn)
    log.info("App connected (pending). Waiting for a browser to claim a session.")
    await conn.run()
    log.info("App disconnected.")

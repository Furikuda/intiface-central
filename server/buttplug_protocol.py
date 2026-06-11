"""Tiny builders for the Buttplug messages we need as a *client*.

We speak spec version 3 (the app's server down-negotiates from v4), which keeps
actuator control to the simple ScalarCmd. Every Buttplug message goes over the
wire as a JSON array of objects, each shaped ``{"MessageType": {"Id": n, ...}}``.
These helpers return the single message object; the bridge wraps it in a list.
"""

MESSAGE_VERSION = 3


def request_server_info(msg_id: int, client_name: str) -> dict:
    return {
        "RequestServerInfo": {
            "Id": msg_id,
            "ClientName": client_name,
            "MessageVersion": MESSAGE_VERSION,
        }
    }


def request_device_list(msg_id: int) -> dict:
    return {"RequestDeviceList": {"Id": msg_id}}


def start_scanning(msg_id: int) -> dict:
    return {"StartScanning": {"Id": msg_id}}


def stop_scanning(msg_id: int) -> dict:
    return {"StopScanning": {"Id": msg_id}}


def ping(msg_id: int) -> dict:
    return {"Ping": {"Id": msg_id}}


def scalar_cmd(msg_id: int, device_index: int, scalars: list[dict]) -> dict:
    """scalars: list of {"Index": int, "Scalar": 0.0-1.0, "ActuatorType": str}."""
    return {
        "ScalarCmd": {
            "Id": msg_id,
            "DeviceIndex": device_index,
            "Scalars": scalars,
        }
    }


def stop_device_cmd(msg_id: int, device_index: int) -> dict:
    return {"StopDeviceCmd": {"Id": msg_id, "DeviceIndex": device_index}}

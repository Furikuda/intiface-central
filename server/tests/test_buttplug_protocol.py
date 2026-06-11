import buttplug_protocol as proto


def test_message_version_is_three():
    assert proto.MESSAGE_VERSION == 3


def test_request_server_info():
    msg = proto.request_server_info(7, "Bob")
    assert msg == {
        "RequestServerInfo": {"Id": 7, "ClientName": "Bob", "MessageVersion": 3}
    }


def test_request_device_list():
    assert proto.request_device_list(3) == {"RequestDeviceList": {"Id": 3}}


def test_start_and_stop_scanning():
    assert proto.start_scanning(1) == {"StartScanning": {"Id": 1}}
    assert proto.stop_scanning(2) == {"StopScanning": {"Id": 2}}


def test_ping():
    assert proto.ping(9) == {"Ping": {"Id": 9}}


def test_scalar_cmd_passes_scalars_through():
    scalars = [{"Index": 0, "Scalar": 0.5, "ActuatorType": "Vibrate"}]
    msg = proto.scalar_cmd(4, 2, scalars)
    assert msg == {"ScalarCmd": {"Id": 4, "DeviceIndex": 2, "Scalars": scalars}}
    # the same list object is referenced, not copied — fine, but assert contents
    assert msg["ScalarCmd"]["Scalars"][0]["ActuatorType"] == "Vibrate"


def test_stop_device_cmd():
    assert proto.stop_device_cmd(5, 1) == {"StopDeviceCmd": {"Id": 5, "DeviceIndex": 1}}


def test_every_builder_carries_an_id():
    builders = [
        proto.request_server_info(1, "x"),
        proto.request_device_list(2),
        proto.start_scanning(3),
        proto.stop_scanning(4),
        proto.ping(5),
        proto.scalar_cmd(6, 0, []),
        proto.stop_device_cmd(7, 0),
    ]
    ids = [next(iter(b.values()))["Id"] for b in builders]
    assert ids == [1, 2, 3, 4, 5, 6, 7]

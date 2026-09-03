from virtual_gamepad_client import JsonFileTransport, VirtualGamepadClient


def test_button_and_axis_commands_use_protocol_envelope():
    transport = JsonFileTransport()
    client = VirtualGamepadClient(transport=transport)

    client.press("A")
    client.set_axis("left_y", 32767, ttl_ms=250)

    assert transport.requests[0]["type"] == "button"
    assert transport.requests[0]["payload"] == {
        "source": "automation",
        "button": "A",
        "action": "press",
    }
    assert transport.requests[1]["payload"]["ttlMs"] == 250


def test_errors_are_exposed_as_virtual_gamepad_errors():
    transport = JsonFileTransport([{"ok": False, "error": {"code": "invalid_argument", "message": "bad"}}])
    client = VirtualGamepadClient(transport=transport)

    try:
        client.start()
    except Exception as exc:
        assert "invalid_argument" in str(exc)
    else:
        raise AssertionError("expected host error")

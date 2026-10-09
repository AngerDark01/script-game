from auto_modules.adapters.virtual_gamepad import ProgramGamepadOutput
import pytest


def test_program_output_uses_lease_not_mapping_start_and_zero_stops_immediately():
    class Client:
        calls = []
        def pause(self, controller):
            self.calls.append(("pause", {"controller": controller}))
        def request(self, name, payload):
            self.calls.append((name, payload))
            return {'token': 'test'}
    client = Client()
    output = ProgramGamepadOutput(client, controller=2)
    with pytest.raises(RuntimeError): output.write((1, 0))
    output.start()
    output.write((0, 1), valid_for_ms=35)
    assert client.calls[-1][1]['state']['leftStickY'] < 0
    assert client.calls[-1][1]['ttlMs'] == 35
    output.write((0, 0))
    assert client.calls[-1][1]['state']['leftStickY'] == 0
    output.stop()
    assert all(name != 'start' for name, _ in client.calls)
    assert client.calls[0] == ("pause", {"controller": 2})


def test_program_output_heartbeat_renews_session_without_writing_state():
    class Client:
        def __init__(self):
            self.calls = []
        def pause(self, controller):
            self.calls.append(("pause", controller))
        def request(self, name, payload):
            self.calls.append((name, payload))
            return {"token": "test"} if name == "program.acquire" else {"accepted": True}

    client = Client()
    output = ProgramGamepadOutput(client, controller=2, heartbeat_interval_ms=900)
    output.start()
    assert output.heartbeat()
    assert [name for name, _ in client.calls].count("program.heartbeat") == 1
    assert [name for name, _ in client.calls].count("program.state") == 0
    output.stop()


def test_program_output_heartbeat_runs_without_control_writes():
    import time

    class Client:
        def __init__(self):
            self.calls = []
        def pause(self, controller):
            pass
        def request(self, name, payload):
            self.calls.append(name)
            return {"token": "test"} if name == "program.acquire" else {"accepted": True}

    client = Client()
    output = ProgramGamepadOutput(client, controller=2, heartbeat_interval_ms=20)
    output.start()
    time.sleep(0.075)
    output.stop()
    assert client.calls.count("program.heartbeat") >= 2
    assert client.calls.count("program.state") == 0


def test_program_output_falls_back_to_state_heartbeat_when_host_lacks_command():
    class Client:
        def __init__(self):
            self.calls = []

        def pause(self, controller):
            pass

        def request(self, name, payload):
            self.calls.append((name, payload))
            if name == "program.acquire":
                return {"token": "test"}
            if name == "program.heartbeat":
                raise RuntimeError("invalid_argument: Unknown program command.")
            return {"accepted": True}

    client = Client()
    output = ProgramGamepadOutput(client, controller=2, heartbeat_interval_ms=900)
    output.start()
    output.write((0.0, 0.0))
    assert output.heartbeat() is True
    # Once the capability probe sees an older Host, remain on the compatible
    # state heartbeat path; do not retry the unsupported command each tick.
    assert output.heartbeat() is True
    assert [name for name, _ in client.calls].count("program.heartbeat") == 1
    assert [name for name, _ in client.calls].count("program.state") >= 3
    output.stop()


def test_program_output_close_releases_lease_and_closes_dedicated_client():
    class Client:
        def __init__(self):
            self.calls = []
            self.closed = False
        def pause(self, controller):
            self.calls.append(("pause", controller))
        def request(self, name, payload):
            self.calls.append((name, payload))
            return {"token": "test"}
        def close(self):
            self.closed = True

    client = Client()
    output = ProgramGamepadOutput(client, controller=1)
    output.start()
    output.close()
    assert client.closed
    assert [name for name, _ in client.calls if name == "program.release"]


def test_program_output_acquire_waits_for_a_host_tick_after_pause(monkeypatch):
    import auto_modules.adapters.virtual_gamepad.program_output as module

    ticks = iter((100, 100, 101))

    class Client:
        def __init__(self):
            self.calls = []

        def pause(self, controller):
            self.calls.append(("pause", controller))

        def request(self, name, payload):
            self.calls.append((name, payload))
            return {"token": "test"}

    monkeypatch.setattr(module, "host_clock_ms", lambda: next(ticks))
    client = Client()
    output = module.ProgramGamepadOutput(client, controller=1)

    output.start()

    acquire = next(payload for name, payload in client.calls if name == "program.acquire")
    assert acquire["requestedAtMs"] == 101


def test_program_output_diagnostics_reads_host_status_and_controller_state():
    class Client:
        def status(self):
            return {"connected": True, "controllers": [{"number": 2, "source": "program"}]}

        def state(self, controller):
            assert controller == 2
            return {"leftStickX": 1200, "leftStickY": -2400}

    output = ProgramGamepadOutput(Client(), controller=2)
    diagnostics = output.diagnostics()
    assert diagnostics["controller"] == 2
    assert diagnostics["acquired"] is False
    assert diagnostics["status"]["connected"] is True
    assert diagnostics["state"]["leftStickY"] == -2400
    assert diagnostics["diagnostics_elapsed_ms"] >= 0
    assert diagnostics["last_host_request_ms"] == 0


def test_program_output_diagnostics_exposes_last_transformed_command():
    class Client:
        def pause(self, controller):
            pass

        def request(self, name, payload):
            if name == "program.acquire":
                return {"token": "test"}
            return {"accepted": True}

        def status(self):
            return {"connected": True}

        def state(self, controller):
            return {"leftStickX": 1, "leftStickY": 2}

    output = ProgramGamepadOutput(Client(), controller=1, basis=(1.0, 0.0, 0.0, -1.0))
    output.start()
    output.write((0.25, -0.5), elapsed_ms=50, valid_for_ms=80)

    command = output.diagnostics()["last_command"]
    assert command["input_vector"] == (0.25, -0.5)
    assert command["input_magnitude"] == pytest.approx(0.5590169944)
    assert command["basis_vector"] == (0.25, 0.5)
    assert command["basis_magnitude"] == pytest.approx(0.5590169944)
    assert command["ttl_ms"] == 80
    assert command["axes"][1] > 0
    assert command["axis_magnitude"] > 0
    assert command["host_request_ms"] >= 0
    assert output.diagnostics()["last_host_request_ms"] >= 0


def test_successful_program_write_reports_effective_axes_and_ttl():
    class Client:
        def pause(self, controller): pass
        def request(self, name, payload):
            return {"token": "test"} if name == "program.acquire" else {"accepted": True}

    output = ProgramGamepadOutput(Client(), controller=1, basis=(0.5, -0.5, 0.5, 0.5), ttl_ms=120)
    output.start()
    receipt = output.write((0.6, 0.0), elapsed_ms=200)
    assert receipt.ttl_ms == 120
    assert receipt.accepted_at_ms > 0
    assert receipt.effective_input_vector[0] > 0
    assert abs(receipt.effective_input_vector[1]) < 0.02


def test_failed_program_write_does_not_report_accepted_motion():
    class Client:
        def pause(self, controller): pass
        def request(self, name, payload):
            if name == "program.state":
                raise RuntimeError("Host rejected state")
            return {"token": "test"}

    output = ProgramGamepadOutput(Client(), controller=1)
    output.start()
    with pytest.raises(RuntimeError, match="Host rejected"):
        output.write((1.0, 0.0))


def test_program_output_rearms_only_current_controller_after_session_expiry_and_keeps_heartbeat():
    class Client:
        def __init__(self):
            self.calls = []
            self.acquire_count = 0
            self.expired_once = True

        def pause(self, controller):
            self.calls.append(("pause", controller))

        def request(self, name, payload):
            self.calls.append((name, payload))
            if name == "program.acquire":
                self.acquire_count += 1
                return {"token": f"token-{self.acquire_count}"}
            if name == "program.heartbeat" and self.expired_once:
                self.expired_once = False
                raise RuntimeError("Program session expired or was revoked")
            return {"accepted": True}

    client = Client()
    output = ProgramGamepadOutput(client, controller=2, heartbeat_interval_ms=900)
    output.start()
    output.write((0.0, 0.0))
    assert output.heartbeat() is False
    assert output.token is None
    output.rearm()
    assert output.token == "token-2"
    assert [name for name, _payload in client.calls].count("program.acquire") == 2
    assert all(payload == 2 for name, payload in client.calls if name == "pause")
    assert output.heartbeat() is True
    diagnostics = output.snapshot()
    assert diagnostics["acquired"] is True
    assert diagnostics["last_command"]["input_vector"] == (0.0, 0.0)
    output.stop()

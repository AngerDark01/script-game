from auto_modules.adapters.virtual_gamepad import ProgramGamepadOutput
import pytest


def test_program_output_uses_lease_not_mapping_start_and_zero_stops_immediately():
    class Client:
        calls = []
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

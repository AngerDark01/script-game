import unittest
from pathlib import Path
from unittest.mock import Mock

from auto_modules.ui.gamepad.host_manager import GamepadHostManager


class _FakeClient:
    def __init__(self, *, connect_error: Exception | None = None):
        self.connect_error = connect_error
        self.calls: list[tuple] = []

    def connect(self, timeout: float = 5.0) -> None:
        self.calls.append(("connect", timeout))
        if self.connect_error is not None:
            raise self.connect_error

    def reset(self, controller: int) -> None:
        self.calls.append(("reset", controller))

    def pause(self, controller: int) -> None:
        self.calls.append(("pause", controller))
        if getattr(self, "pause_error", None) is not None:
            raise self.pause_error

    def close(self) -> None:
        self.calls.append(("close",))


class GamepadHostManagerTests(unittest.TestCase):
    def test_start_attaches_to_an_existing_host_without_spawning_or_owning_it(self):
        probe = _FakeClient()
        spawn = Mock()
        manager = GamepadHostManager(client_factory=lambda: probe, process_factory=spawn)

        result = manager.start(timeout=0.01)

        self.assertTrue(result.connected)
        self.assertFalse(result.owns_host)
        self.assertFalse(manager.owns_host)
        spawn.assert_not_called()
        self.assertEqual([("connect", 0.1), ("close",)], probe.calls)

    def test_start_launches_and_waits_for_a_host_when_the_pipe_is_initially_unavailable(self):
        unavailable = _FakeClient(connect_error=OSError("pipe unavailable"))
        ready = _FakeClient()
        process = Mock()
        spawn = Mock(return_value=process)
        clients = iter((unavailable, ready))
        manager = GamepadHostManager(
            client_factory=lambda: next(clients),
            process_factory=spawn,
            host_command_factory=lambda: ["dotnet", "exec", "host.dll"],
            host_working_directory=Path("D:/host"),
        )

        result = manager.start(timeout=0.1)

        self.assertTrue(result.connected)
        self.assertTrue(result.owns_host)
        self.assertTrue(manager.owns_host)
        spawn.assert_called_once()
        self.assertEqual([("connect", 0.1), ("close",)], unavailable.calls)
        self.assertEqual([("connect", 0.1), ("close",)], ready.calls)

    def test_shutdown_resets_and_pauses_both_controllers_then_stops_only_owned_host(self):
        cleanup = _FakeClient()
        process = Mock()
        manager = GamepadHostManager(client_factory=lambda: cleanup, process_factory=Mock())
        manager._host_process = process
        manager._owns_host = True

        result = manager.shutdown()

        self.assertTrue(result.succeeded)
        self.assertEqual(
            [
                ("connect", 0.25),
                ("reset", 1),
                ("pause", 1),
                ("reset", 2),
                ("pause", 2),
                ("close",),
            ],
            cleanup.calls,
        )
        process.terminate.assert_called_once()
        self.assertFalse(manager.owns_host)

    def test_shutdown_never_terminates_a_host_that_the_workbench_only_attached_to(self):
        cleanup = _FakeClient()
        process = Mock()
        manager = GamepadHostManager(client_factory=lambda: cleanup, process_factory=Mock())
        manager._host_process = process
        manager._owns_host = False

        result = manager.shutdown()

        self.assertTrue(result.succeeded)
        process.terminate.assert_not_called()

    def test_shutdown_stops_an_owned_host_even_when_pipe_cleanup_cannot_be_confirmed(self):
        cleanup = _FakeClient()
        cleanup.pause_error = OSError("host stopped responding")
        process = Mock()
        manager = GamepadHostManager(client_factory=lambda: cleanup, process_factory=Mock())
        manager._host_process = process
        manager._owns_host = True

        result = manager.shutdown()

        self.assertFalse(result.succeeded)
        self.assertTrue(result.stopped_owned_host)
        self.assertTrue(result.errors)
        process.terminate.assert_called_once()

    def test_failed_readiness_stops_the_process_started_by_this_manager(self):
        unavailable_probe = _FakeClient(connect_error=OSError("unavailable"))
        unavailable_after_start = _FakeClient(connect_error=OSError("unavailable"))
        process = Mock()
        clients = iter((unavailable_probe, unavailable_after_start))
        manager = GamepadHostManager(
            client_factory=lambda: next(clients),
            process_factory=Mock(return_value=process),
            host_command_factory=lambda: ["dotnet", "exec", "host.dll"],
            host_working_directory=Path("D:/host"),
        )

        result = manager.start(timeout=0)

        self.assertFalse(result.connected)
        self.assertFalse(result.owns_host)
        process.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()

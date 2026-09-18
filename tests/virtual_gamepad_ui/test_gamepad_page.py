from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSplitter, QWidget

from auto_modules.ui.virtual_gamepad.gamepad_page import GamepadPage, _call_controller_method
from auto_modules.ui.virtual_gamepad.main_window import MainWindow
from auto_modules.ui.virtual_gamepad.models import CONTROLS


class FakeClient:
    def __init__(self, *, failing_actions: set[tuple[str, int]] | None = None) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.lifecycle_calls: list[tuple[str, int, str | None, int | None]] = []
        self.requests: list[tuple[str, dict]] = []
        self.connect_calls = 0
        self.failing_actions = failing_actions or set()

    def connect(self, timeout: float = 5.0) -> None:
        self.connect_calls += 1

    def status(self) -> dict:
        return {
            "runState": "paused",
            "driverInstalled": True,
            "deviceConnected": True,
            "message": "",
        }

    def state(self, _controller: int = 1) -> dict:
        return {}

    def request(self, message_type: str, payload: dict | None = None) -> dict:
        self.requests.append((message_type, payload or {}))
        return {}

    def reset(self, controller: int, *, source: str | None = None, sequence: int | None = None) -> None:
        self.calls.append(("reset", controller))
        self.lifecycle_calls.append(("reset", controller, source, sequence))
        if ("reset", controller) in self.failing_actions:
            raise RuntimeError(f"controller {controller} reset failed")

    def start(self, controller: int, *, source: str | None = None, sequence: int | None = None) -> None:
        self.calls.append(("start", controller))
        self.lifecycle_calls.append(("start", controller, source, sequence))

    def emergency_reset(self) -> None:
        self.calls.append(("emergency_reset", None))

    def pause(self, controller: int, *, source: str | None = None, sequence: int | None = None) -> None:
        self.calls.append(("pause", controller))
        self.lifecycle_calls.append(("pause", controller, source, sequence))
        if ("pause", controller) in self.failing_actions:
            raise RuntimeError(f"controller {controller} is unavailable")

    def close(self) -> None:
        self.calls.append(("close", None))


class BlockingStatusClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.status_started = threading.Event()
        self.release_status = threading.Event()
        self.status_calls = 0
        self.max_concurrent_status = 0
        self._active_status = 0
        self._status_lock = threading.Lock()

    def status(self) -> dict:
        with self._status_lock:
            self.status_calls += 1
            self._active_status += 1
            self.max_concurrent_status = max(self.max_concurrent_status, self._active_status)
        self.status_started.set()
        self.release_status.wait(1.0)
        with self._status_lock:
            self._active_status -= 1
        return super().status()


class CancellableBlockingStatusClient(BlockingStatusClient):
    def close(self) -> None:
        self.release_status.set()
        super().close()


class BlockingStartClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.start_called = threading.Event()
        self.release_start = threading.Event()

    def start(self, controller: int, *, source: str | None = None, sequence: int | None = None) -> None:
        self.calls.append(("start", controller))
        self.lifecycle_calls.append(("start", controller, source, sequence))
        self.start_called.set()
        self.release_start.wait(1.0)


class TransientPauseClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.pause_attempts: dict[int, int] = {}

    def pause(self, controller: int, *, source: str | None = None, sequence: int | None = None) -> None:
        super().pause(controller, source=source, sequence=sequence)
        self.pause_attempts[controller] = self.pause_attempts.get(controller, 0) + 1
        if controller == 1 and self.pause_attempts[controller] == 1:
            raise RuntimeError("temporary pause failure")


class BlockingCleanupPauseClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.pause_started = threading.Event()
        self.release_pause = threading.Event()

    def pause(self, controller: int, *, source: str | None = None, sequence: int | None = None) -> None:
        super().pause(controller, source=source, sequence=sequence)
        self.pause_started.set()
        self.release_pause.wait(1.0)


class TypeErrorStartClient(FakeClient):
    def start(self, controller: int, *, source: str | None = None, sequence: int | None = None) -> None:
        raise TypeError("action implementation failed")


class KeywordOnlyLifecycleClient:
    def __init__(self) -> None:
        self.received: tuple[int, str | None, int | None] | None = None

    def start(self, *, controller: int, source: str | None = None, sequence: int | None = None) -> None:
        self.received = (controller, source, sequence)


class RecoveringClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []
        self.fail_next_status = True

    def connect(self, timeout: float = 5.0) -> None:
        self.events.append("connect")
        super().connect(timeout)

    def status(self) -> dict:
        self.events.append("status")
        if self.fail_next_status:
            self.fail_next_status = False
            raise OSError("dead line transport")
        return {
            "runState": "ready",
            "driverInstalled": True,
            "deviceConnected": True,
            "message": "",
        }

    def close(self) -> None:
        self.events.append("close")
        super().close()


class ProfileApplyRecoveringClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_profile_apply = True

    def request(self, message_type: str, payload: dict | None = None) -> dict:
        result = super().request(message_type, payload)
        if message_type == "set_config" and self.fail_next_profile_apply:
            self.fail_next_profile_apply = False
            raise OSError("profile pipe write failed")
        return result


class GamepadPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, predicate, timeout: float = 1.5) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(0.005)
        self.fail("condition did not become true before timeout")

    def test_page_selects_controller_two_and_keeps_mouse_bindings_dropdown_based(self) -> None:
        with tempfile.TemporaryDirectory() as root, self.subTest("select controller two"):
            client = FakeClient()
            page = GamepadPage(client, profile_root=Path(root))
            self.addCleanup(page.deleteLater)
            self.addCleanup(page.shutdown)
            page.profiles[1].bindings = {"A": ["keyboard:Space"]}
            page.show()
            self.wait_until(lambda: not page._poll_in_flight and page._profiles_applied)
            page._select_controller(2)
            page._select_control("A")
            client.requests.clear()

            index = page.mouse_combo.findData("mouse:right")
            self.assertGreaterEqual(index, 0)
            page.mouse_combo.setCurrentIndex(index)

            expected_payload = {**page.profiles[2].to_payload(), "controller": 2}
            self.wait_until(lambda: client.requests == [("set_config", expected_payload)])

            self.assertEqual(page.selected_controller, 2)
            self.assertEqual(page.profiles[2].bindings["A"], ["mouse:right"])
            self.assertEqual(page.profiles[1].bindings["A"], ["keyboard:Space"])
            self.assertEqual(
                client.requests,
                [("set_config", expected_payload)],
            )

    def test_shutdown_surfaces_a_permanent_cleanup_failure_after_bounded_retries(self) -> None:
        page_client = FakeClient()
        cleanup_client = FakeClient(failing_actions={("pause", 1)})
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(
                page_client,
                profile_root=Path(root),
                client_factory=lambda: cleanup_client,
            )
        self.addCleanup(page.deleteLater)

        outcomes: list[tuple[bool, str]] = []
        page.shutdown_finished.connect(lambda succeeded, message: outcomes.append((succeeded, message)))
        page.shutdown()
        self.wait_until(lambda: cleanup_client.calls[-1:] == [("close", None)])
        self.wait_until(lambda: bool(outcomes))

        self.assertEqual(
            cleanup_client.calls[-6:],
            [("reset", 1), ("pause", 1), ("pause", 1), ("reset", 2), ("pause", 2), ("close", None)],
        )
        self.assertEqual(page_client.calls, [("close", None)])
        self.assertFalse(outcomes[-1][0])
        self.assertIn("Controller 1 pause failed", outcomes[-1][1])
        self.assertIn("Controller 1 pause failed", page.message_label.text())
        self.assertFalse(page._shutting_down)
        self.assertTrue(page._shutdown_failed)

    def test_shutdown_retries_a_transient_pause_failure_and_reports_success(self) -> None:
        page_client = FakeClient()
        cleanup_client = TransientPauseClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(
                page_client,
                profile_root=Path(root),
                client_factory=lambda: cleanup_client,
            )
        self.addCleanup(page.deleteLater)

        outcomes: list[tuple[bool, str]] = []
        page.shutdown_finished.connect(lambda succeeded, message: outcomes.append((succeeded, message)))
        page.shutdown()
        self.wait_until(lambda: bool(outcomes))

        self.assertEqual(outcomes, [(True, "")])
        self.assertEqual(cleanup_client.pause_attempts[1], 2)
        self.assertEqual(cleanup_client.pause_attempts[2], 1)
        self.assertTrue(page._shutting_down)
        self.assertFalse(page._shutdown_failed)

    def test_demo_policy_skips_pipe_connect_and_saved_profile_apply(self) -> None:
        client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root), demo=True)
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)

        self.assertEqual(client.connect_calls, 0)
        self.assertEqual(client.requests, [])

    def test_hidden_page_stops_polling_and_never_overlaps_status_requests(self) -> None:
        client = BlockingStatusClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root))
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        for _ in range(4):
            self.app.processEvents()
            time.sleep(0.005)
        self.assertEqual(client.status_calls, 0)
        started_at = time.monotonic()
        page.show()
        self.wait_until(client.status_started.is_set, timeout=0.5)
        self.assertLess(time.monotonic() - started_at, 0.5)

        page.refresh()
        page.refresh()
        page.hide()
        client.release_status.set()
        self.wait_until(lambda: not page._poll_in_flight)
        calls_after_hide = client.status_calls
        for _ in range(20):
            self.app.processEvents()
            time.sleep(0.01)

        self.assertEqual(client.max_concurrent_status, 1)
        self.assertEqual(client.status_calls, calls_after_hide)
        self.assertFalse(page._timer.isActive())

    def test_failed_pipe_is_closed_then_reconnected_on_the_retry_backoff(self) -> None:
        client = RecoveringClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root))
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        page.POLL_FAILURE_INITIAL_MS = 5
        page.POLL_FAILURE_MAX_MS = 5
        page._failure_delay_ms = 5
        page.show()

        self.wait_until(lambda: page.state_label.text() == "State: ready")

        self.assertGreaterEqual(client.connect_calls, 2)
        self.assertGreaterEqual(client.calls.count(("close", None)), 1)
        self.assertLess(client.events.index("close"), len(client.events) - 1)
        self.assertEqual(page.message_label.text(), "")

    def test_malformed_profile_falls_back_without_preventing_page_construction(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            profile_root = Path(root)
            (profile_root / "controller-1.json").write_text("{not valid json", encoding="utf-8")
            page = GamepadPage(FakeClient(), profile_root=profile_root, demo=True)
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.profiles[1].bindings, {})
        self.assertIn("Controller 1 profile could not be loaded", page.message_label.text())

    def test_profile_apply_failure_retries_on_backoff_and_clears_after_full_success(self) -> None:
        client = ProfileApplyRecoveringClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root))
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        page._failure_delay_ms = 100
        page.POLL_FAILURE_MAX_MS = 100
        page.show()

        self.wait_until(lambda: bool(page._profile_apply_error))
        failed_request_count = len(client.requests)
        self.assertIn("Could not apply saved profiles", page.message_label.text())
        for _ in range(8):
            self.app.processEvents()
            time.sleep(0.005)
        self.assertEqual(len(client.requests), failed_request_count)

        self.wait_until(lambda: page._profiles_applied and not page._profile_apply_error)
        self.assertGreaterEqual(len(client.requests), failed_request_count + 2)

    def test_binding_changed_during_poll_is_sent_in_a_follow_up_versioned_apply(self) -> None:
        client = BlockingStatusClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root))
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        page.show()
        self.wait_until(client.status_started.is_set)

        page._select_controller(2)
        page._select_control("A")
        index = page.mouse_combo.findData("mouse:right")
        self.assertGreaterEqual(index, 0)
        page.mouse_combo.setCurrentIndex(index)
        client.release_status.set()

        expected_payload = {**page.profiles[2].to_payload(), "controller": 2}
        self.wait_until(
            lambda: page._profiles_applied
            and any(message == "set_config" and payload == expected_payload for message, payload in client.requests)
        )

    def test_page_buttons_dispatch_pipe_commands_without_blocking_the_gui_thread(self) -> None:
        client = BlockingStartClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root), demo=True)
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)

        started_at = time.monotonic()
        page._start()
        self.assertLess(time.monotonic() - started_at, 0.1)
        self.wait_until(client.start_called.is_set)
        client.release_start.set()
        self.wait_until(lambda: not page._command_in_flight)

    def test_lifecycle_controls_wait_for_profiles_then_send_fenced_start_once(self) -> None:
        client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root))
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)

        page._start()
        self.assertNotIn(("start", 1), client.calls)
        self.assertFalse(page.start_button.isEnabled())
        self.assertIn("preparing profiles", page.message_label.text())

        page.show()
        self.wait_until(page._lifecycle_ready)
        page._start()
        self.wait_until(lambda: not page._command_in_flight and bool(client.lifecycle_calls))

        starts = [call for call in client.lifecycle_calls if call[0] == "start"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0][2], page._lifecycle_source)
        self.assertGreater(starts[0][3] or 0, 0)

    def test_profile_edit_disables_lifecycle_controls_until_the_new_version_is_applied(self) -> None:
        client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root))
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        page.show()
        self.wait_until(page._lifecycle_ready)
        page._select_control("A")

        index = page.keyboard_combo.findData("keyboard:J")
        self.assertGreaterEqual(index, 0)
        page.keyboard_combo.setCurrentIndex(index)
        page._set_keyboard_binding()

        self.assertFalse(page.start_button.isEnabled())
        self.wait_until(page._lifecycle_ready)
        self.assertTrue(page.start_button.isEnabled())

    def test_switching_controls_updates_every_binding_editor_field_from_one_profile_source(self) -> None:
        """A controller-diagram click must not leave keyboard data from the prior control."""
        client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root), demo=True)
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        page.profiles[1].bindings = {
            "A": ["keyboard:Space"],
            "RightStick": ["mouse:move_x", "mouse:move_y"],
        }

        page._select_control("A")
        self.assertEqual(page.selected_label.text(), "A")
        self.assertEqual(page.binding_edit.text(), "keyboard:Space")
        self.assertEqual(page.keyboard_combo.currentData(), "keyboard:Space")
        self.assertEqual(page.mouse_combo.currentData(), "")

        page.controller.control_clicked.emit("RightStick")

        self.assertEqual(page.selected_label.text(), "RightStick")
        self.assertEqual(page.binding_edit.text(), "")
        self.assertEqual(page.keyboard_combo.currentData(), "")
        self.assertEqual(page.mouse_combo.currentData(), "mouse:move_x")

    def test_binding_editor_is_compact_and_does_not_use_a_full_height_splitter(self) -> None:
        client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(client, profile_root=Path(root), demo=True)
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        page.resize(1200, 760)
        page.show()
        self.app.processEvents()

        binding_card = page.findChild(QWidget, "bindingCard")
        self.assertIsNotNone(binding_card)
        self.assertFalse(page.findChildren(QSplitter))
        self.assertEqual(page.control_combo.count(), len(CONTROLS))
        self.assertEqual(page._selected_control(), "A")
        self.assertLessEqual(binding_card.width(), 430)
        self.assertGreater(page.controller.width(), binding_card.width())

    def test_cleanup_sequences_are_newer_than_a_dispatched_lifecycle_command(self) -> None:
        page_client = BlockingStartClient()
        cleanup_client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(
                page_client,
                profile_root=Path(root),
                demo=True,
                client_factory=lambda: cleanup_client,
            )
        self.addCleanup(page.deleteLater)

        page._start()
        self.wait_until(page_client.start_called.is_set)
        start = page_client.lifecycle_calls[-1]
        page.shutdown()
        self.assertFalse(page.start_button.isEnabled())
        self.wait_until(lambda: cleanup_client.calls[-1:] == [("close", None)])
        page_client.release_start.set()

        cleanup_lifecycle = [call for call in cleanup_client.lifecycle_calls if call[0] in {"reset", "pause"}]
        self.assertEqual(len(cleanup_lifecycle), 4)
        self.assertTrue(all(call[2] == start[2] for call in cleanup_lifecycle))
        self.assertTrue(all((call[3] or 0) > (start[3] or 0) for call in cleanup_lifecycle))

    def test_action_type_error_is_not_reinterpreted_as_a_legacy_signature(self) -> None:
        with self.assertRaisesRegex(TypeError, "action implementation failed"):
            _call_controller_method(
                TypeErrorStartClient(),
                "start",
                1,
                source="virtual-gamepad-page:test",
                sequence=1,
            )

    def test_keyword_only_lifecycle_client_receives_controller_and_fence_metadata(self) -> None:
        client = KeywordOnlyLifecycleClient()
        _call_controller_method(
            client,
            "start",
            2,
            source="virtual-gamepad-page:test",
            sequence=7,
        )

        self.assertEqual(client.received, (2, "virtual-gamepad-page:test", 7))

    def test_main_window_keeps_open_when_cleanup_fails(self) -> None:
        page_client = FakeClient()
        cleanup_client = FakeClient(failing_actions={("pause", 1)})
        with tempfile.TemporaryDirectory() as root:
            window = MainWindow(
                page_client,
                profile_path=Path(root),
                client_factory=lambda: cleanup_client,
            )
        self.addCleanup(window.deleteLater)
        window.show()
        self.app.processEvents()

        window.close()
        self.wait_until(lambda: cleanup_client.calls[-1:] == [("close", None)])
        self.wait_until(lambda: not window._close_requested)

        self.assertTrue(window.isVisible())
        self.assertFalse(window._close_approved)
        self.assertIn("Controller 1 pause failed", window.page.message_label.text())

    def test_main_window_only_closes_after_successful_cleanup(self) -> None:
        page_client = FakeClient()
        cleanup_client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            window = MainWindow(
                page_client,
                profile_path=Path(root),
                client_factory=lambda: cleanup_client,
            )
        self.addCleanup(window.deleteLater)
        window.show()
        self.app.processEvents()

        window.close()
        self.wait_until(lambda: not window.isVisible())

        self.assertTrue(window._close_approved)
        self.assertEqual(cleanup_client.calls[-1:], [("close", None)])

    def test_main_window_keeps_open_when_cleanup_times_out(self) -> None:
        page_client = FakeClient()
        cleanup_client = BlockingCleanupPauseClient()
        with tempfile.TemporaryDirectory() as root:
            window = MainWindow(
                page_client,
                profile_path=Path(root),
                client_factory=lambda: cleanup_client,
            )
        self.addCleanup(window.deleteLater)
        window.page.SHUTDOWN_TIMEOUT_MS = 20
        window.show()
        self.app.processEvents()

        window.close()
        self.wait_until(cleanup_client.pause_started.is_set)
        self.wait_until(lambda: not window._close_requested)

        self.assertTrue(window.isVisible())
        self.assertFalse(window._close_approved)
        self.assertIn("Timed out", window.page.message_label.text())
        cleanup_client.release_pause.set()
        self.wait_until(lambda: cleanup_client.calls[-1:] == [("close", None)])

    def test_shutdown_cancels_blocked_poll_before_background_cleanup(self) -> None:
        page_client = CancellableBlockingStatusClient()
        cleanup_client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(
                page_client,
                profile_root=Path(root),
                client_factory=lambda: cleanup_client,
            )
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        page.show()
        self.wait_until(page_client.status_started.is_set)

        started_at = time.monotonic()
        page.shutdown()
        self.assertLess(time.monotonic() - started_at, 0.15)
        self.assertIn(("close", None), page_client.calls)
        self.wait_until(lambda: cleanup_client.calls[-1:] == [("close", None)])
        self.assertEqual(
            cleanup_client.calls[-5:],
            [("reset", 1), ("pause", 1), ("reset", 2), ("pause", 2), ("close", None)],
        )

    def test_hide_cancels_stale_poll_then_show_reconnects_with_a_fresh_page_client(self) -> None:
        blocked_client = CancellableBlockingStatusClient()
        recovered_client = FakeClient()
        with tempfile.TemporaryDirectory() as root:
            page = GamepadPage(
                blocked_client,
                profile_root=Path(root),
                client_factory=lambda: recovered_client,
            )
        self.addCleanup(page.shutdown)
        self.addCleanup(page.deleteLater)
        page.show()
        self.wait_until(blocked_client.status_started.is_set)

        page.hide()
        page.show()
        self.wait_until(lambda: recovered_client.connect_calls > 0 and page.state_label.text() == "State: paused")

        self.assertIn(("close", None), blocked_client.calls)


if __name__ == "__main__":
    unittest.main()

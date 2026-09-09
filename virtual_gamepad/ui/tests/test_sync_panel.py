import os
import time
import threading
import unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from virtual_gamepad_ui.sync_panel import SyncPanel


class Client:
    calls = []
    def connect(self, timeout=0.25): pass
    def close(self): pass
    def request(self, command, payload):
        self.calls.append((command, payload))
        return {"ok": True, "status": {"mode": "off", "deviceId": "local", "name": "电脑 A", "peers": [], "pending": [], "discovered": []}}


class SyncPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])
    def setUp(self):
        Client.calls = []
        self.panel = SyncPanel(Client)
    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
    def wait(self, predicate):
        end = time.monotonic() + 2
        while not predicate() and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertTrue(predicate())
    def test_constructing_panel_does_not_enable_network(self):
        self.assertEqual(Client.calls, [])
        self.assertEqual(self.panel.mode.currentData(), "off")
    def test_apply_keeps_controller_route_and_uses_async_pipe(self):
        self.panel.mode.setCurrentIndex(self.panel.mode.findData("receive"))
        self.panel.c2.setChecked(False)
        self.panel.apply_settings()
        self.wait(lambda: not self.panel.busy)
        command, payload = Client.calls[0]
        self.assertEqual(command, "sync.configure")
        self.assertEqual(payload["mode"], "receive")
        self.assertEqual(payload["controllers"], [1])
    def test_pair_confirmation_requires_user_action(self):
        self.panel.render({"pending": [{"requestId": "r1", "name": "电脑 B", "fingerprint": "123456", "incoming": True}]})
        self.assertEqual(Client.calls, [])
        self.assertEqual(self.panel.pending.count(), 1)
    def test_shutdown_uses_newer_sequence_and_disables_actions(self):
        self.panel.apply_settings()
        self.wait(lambda: not self.panel.busy)
        self.panel.shutdown()
        self.wait(lambda: any(command == "sync.stop" for command, _ in Client.calls))
        self.assertGreater(Client.calls[-1][1]["_uiSequence"], Client.calls[0][1]["_uiSequence"])
        self.assertFalse(self.panel.isEnabled())
    def test_mode_actions_follow_applied_status_not_unsaved_selection(self):
        self.panel.render({"mode": "receive", "networkReady": True})
        self.assertTrue(self.panel.receive_button.isEnabled())
        self.assertTrue(self.panel.code_button.isEnabled())
        self.assertFalse(self.panel.send_button.isEnabled())
        self.panel.mode.setCurrentIndex(self.panel.mode.findData("send"))
        self.assertFalse(self.panel.send_button.isEnabled())
        self.panel.render({"mode": "send", "networkReady": True})
        self.assertTrue(self.panel.send_button.isEnabled())
        self.assertTrue(self.panel.pair_button.isEnabled())
        self.assertFalse(self.panel.receive_button.isEnabled())
        self.panel.render({"mode": "send", "networkReady": False})
        self.assertFalse(self.panel.send_button.isEnabled())
    def test_stop_supersedes_queued_start_and_ignores_late_status(self):
        entered, release = threading.Event(), threading.Event()
        class SlowClient(Client):
            def request(inner, command, payload):
                if command == "sync.status":
                    entered.set()
                    release.wait(1)
                return super().request(command, payload)
        self.panel.factory = SlowClient
        try:
            self.panel.command("sync.status")
            self.wait(entered.is_set)
            self.panel.command("sync.start", {"deviceId": "peer"})
            self.panel.command("sync.stop")
            self.wait(lambda: any(c == "sync.stop" for c, _ in Client.calls))
            self.wait(lambda: not self.panel.busy)
            release.set()
            self.wait(lambda: any(c == "sync.status" for c, _ in Client.calls))
            self.assertFalse(any(c == "sync.start" for c, _ in Client.calls))
            self.assertIsNone(self.panel._pending_command)
        finally:
            release.set()
    def test_old_host_without_sync_does_not_block_shutdown(self):
        class OldClient(Client):
            def request(inner, command, payload):
                raise RuntimeError("unknown_type: Unknown message type: sync.stop")
        self.panel.factory = OldClient
        result = []
        self.panel.shutdown_finished.connect(lambda ok, error: result.append(ok))
        self.panel.shutdown()
        self.wait(lambda: bool(result))
        self.assertEqual(result, [True])
    def test_subsequent_stops_are_serialized_so_scopes_cannot_be_lost(self):
        for first, second in (({}, {"deviceId": "B"}), ({"deviceId": "A"}, {"deviceId": "B"})):
            entered, release = threading.Event(), threading.Event()
            received = []
            class BlockingStop(Client):
                def request(inner, command, payload):
                    received.append((command, payload))
                    if len(received) == 1:
                        entered.set()
                        release.wait(1)
                    return super().request(command, payload)
            self.panel.factory = BlockingStop
            try:
                self.panel.command("sync.stop", first)
                self.wait(entered.is_set)
                self.panel.command("sync.stop", second)
                self.assertEqual(len(received), 1)
                release.set()
                self.wait(lambda: len(received) == 2 and not self.panel.busy)
                self.assertEqual(received[0][1].get("deviceId"), first.get("deviceId"))
                self.assertEqual(received[1][1].get("deviceId"), second.get("deviceId"))
                self.assertGreater(received[1][1]["_uiSequence"], received[0][1]["_uiSequence"])
            finally:
                release.set()
    def test_real_stop_failure_is_not_masked(self):
        class FailedClient(Client):
            def request(inner, command, payload):
                raise RuntimeError("Host pipe I/O failed")
        self.panel.factory = FailedClient
        result = []
        self.panel.shutdown_finished.connect(lambda ok, error: result.append(ok))
        self.panel.shutdown()
        self.wait(lambda: bool(result))
        self.assertEqual(result, [False])

"""Latest-only output actor: GUI methods never enter Host or scheduler locks."""
from __future__ import annotations

from collections import deque
import logging
import threading
import time

_LOG = logging.getLogger("auto_modules.poe2_live_terrain.follow_engine")


class AsyncSnapshotOutput:
    def __init__(self, adapter, *, io_timeout_s=1.5):
        self.adapter = adapter
        self.io_timeout_s = float(io_timeout_s)
        self._condition = threading.Condition()
        self._latest = None
        self._neutral = False
        self._stop = False
        self._thread = None
        self._receipts = deque(maxlen=128)
        self._diagnostics = {
            "started": False,
            "state": "stopped",
            "last_error": "",
            "failure": None,
        }
        self._busy_since = None
        self._watchdog_stop = threading.Event()
        self._watchdog = None

    def start(self):
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("previous output actor is still running")
            self._latest = None
            self._neutral = self._stop = False
            self._receipts.clear()
            self._diagnostics = {
                "started": False,
                "state": "starting",
                "last_error": "",
                "failure": None,
            }
            watchdog_stop = threading.Event()
            self._watchdog_stop = watchdog_stop
            self._thread = threading.Thread(target=self._run, name="follow-output-actor", daemon=True)
            self._thread.start()
            self._watchdog = threading.Thread(
                target=self._watch,
                args=(watchdog_stop,),
                name="follow-output-watchdog",
                daemon=True,
            )
            self._watchdog.start()
            _LOG.info("step=follow_engine.output_actor_started actor_id=%s thread=%s watchdog=%s", id(self), self._thread.name, self._watchdog.name)

    def apply(self, snapshot):
        with self._condition:
            if not self._stop:
                self._latest = snapshot
                self._condition.notify()

    def neutralize(self):
        with self._condition:
            self._latest = None
            self._neutral = True
            self._condition.notify()

    def poll_receipts(self):
        with self._condition:
            results = tuple(self._receipts)
            self._receipts.clear()
            return results

    def diagnostics(self):
        with self._condition:
            return dict(self._diagnostics)

    def _run(self):
        try:
            with self._condition:
                self._busy_since = time.monotonic()
            try:
                self.adapter.start()
            except Exception as exc:
                with self._condition:
                    # Mark the actor terminal before returning.  A caller can
                    # now distinguish a failed lease from an actor that is
                    # merely still starting, and apply() will refuse to
                    # enqueue snapshots after this point.
                    self._stop = True
                    self._diagnostics = {
                        "started": False,
                        "state": "failed",
                        "last_error": f"{type(exc).__name__}: {exc}",
                        "failure": {
                            "kind": "adapter_start_failed",
                            "type": type(exc).__name__,
                            "message": str(exc),
                        },
                    }
                    self._condition.notify_all()
                _LOG.exception("step=follow_engine.output_actor_start_failed")
                return
            with self._condition:
                self._busy_since = None
                self._diagnostics["started"] = True
                self._diagnostics["state"] = "running"
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._stop or self._neutral or self._latest is not None)
                    if self._stop:
                        break
                    snapshot, self._latest = self._latest, None
                    neutral, self._neutral = self._neutral, False
                    self._busy_since = time.monotonic()
                try:
                    if neutral:
                        self.adapter.neutralize()
                    elif snapshot is not None:
                        self.adapter.apply(snapshot)
                    diagnostics = self.adapter.diagnostics()
                except Exception as exc:
                    diagnostics = {"started": True, "last_error": f"{type(exc).__name__}: {exc}"}
                    _LOG.exception("step=follow_engine.output_actor_error")
                    # No stale lease is treated as movement evidence.
                    try:
                        self.adapter.neutralize()
                    except Exception:
                        pass
                receipts = self.adapter.poll_receipts()
                with self._condition:
                    self._receipts.extend(receipts)
                    self._diagnostics = diagnostics
                    self._busy_since = None
        finally:
            try:
                with self._condition:
                    self._busy_since = time.monotonic()
                self.adapter.stop()
            except Exception as exc:
                _LOG.exception("step=follow_engine.output_actor_cleanup_failed")
                with self._condition:
                    # Preserve the primary adapter-start failure.  Cleanup
                    # errors are still logged, but must not hide the reason
                    # the actor entered its terminal failed state.
                    if self._diagnostics.get("state") != "failed":
                        self._diagnostics["last_error"] = str(exc)
            finally:
                with self._condition:
                    self._busy_since = None
                    self._diagnostics["started"] = False
                    if self._diagnostics.get("state") != "failed":
                        self._diagnostics["state"] = "stopped"
                self._watchdog_stop.set()

    def _watch(self, stop_event):
        while not stop_event.wait(.05):
            with self._condition:
                since = self._busy_since
            if since is not None and time.monotonic() - since > self.io_timeout_s:
                self.adapter.cancel_pending_io()
                with self._condition:
                    self._diagnostics["last_error"] = "output_io_timeout"

    def stop(self, *, force=True):
        _LOG.info("step=follow_engine.output_actor_stop_requested actor_id=%s state=%s", id(self), self.diagnostics().get("state"))
        with self._condition:
            self._latest = None
            self._stop = True
            self._condition.notify()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self.io_timeout_s + .3)
            if thread.is_alive():
                self.adapter.cancel_pending_io()
                raise TimeoutError("output actor did not finish cleanup; retained")
        if self._watchdog is not None:
            self._watchdog.join(timeout=.2)
        _LOG.info("step=follow_engine.output_actor_stopped actor_id=%s state=%s", id(self), self.diagnostics().get("state"))
        self._thread = None

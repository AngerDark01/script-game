"""Small language-neutral client for VirtualGamepadHost's JSON-lines pipe."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, BinaryIO


PIPE_PATH = r"\\.\pipe\AutoModules.VirtualGamepad.v1"


class VirtualGamepadError(RuntimeError):
    """The host rejected a request or could not be reached."""


class VirtualGamepadClient:
    def __init__(self, pipe_path: str = PIPE_PATH, transport: Any | None = None) -> None:
        self.pipe_path = pipe_path
        self._transport = transport
        self._pipe: Any | None = None
        self._lock = threading.Lock()
        self._sequence = 0

    def connect(self, timeout: float = 5.0) -> None:
        if self._transport is not None:
            return
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                self._pipe = open(self.pipe_path, "r+", encoding="utf-8", newline="\n")
                return
            except OSError as exc:
                last_error = exc
                time.sleep(0.05)
        raise VirtualGamepadError(f"Unable to connect to host pipe {self.pipe_path}: {last_error}")

    def close(self) -> None:
        if self._pipe is not None:
            self._pipe.close()
            self._pipe = None
        close = getattr(self._transport, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> "VirtualGamepadClient":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def request(self, message_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._sequence += 1
        message = {"id": str(self._sequence), "type": message_type, "payload": payload or {}}
        with self._lock:
            response = self._request_unlocked(message)
        if not response.get("ok", False):
            error = response.get("error") or {}
            raise VirtualGamepadError(f"{error.get('code', 'host_error')}: {error.get('message', response)}")
        return response.get("payload") or {}

    def _request_unlocked(self, message: dict[str, Any]) -> dict[str, Any]:
        if self._transport is not None:
            return self._transport.request(message)
        if self._pipe is None:
            raise VirtualGamepadError("Client is not connected.")
        self._pipe.write(json.dumps(message, separators=(",", ":")) + "\n")
        self._pipe.flush()
        line = self._pipe.readline()
        if not line:
            raise VirtualGamepadError("Host closed the pipe.")
        return json.loads(line)

    def hello(self) -> dict[str, Any]:
        return self.request("hello")

    def status(self) -> dict[str, Any]:
        return self.request("get_status")

    def state(self) -> dict[str, Any]:
        return self.request("get_state")

    def start(self) -> None:
        self.request("start")

    def pause(self) -> None:
        self.request("pause")

    def reset(self) -> None:
        self.request("reset")

    def emergency_reset(self) -> None:
        self.request("emergency_reset")

    def press(self, button: str, source: str = "automation", ttl_ms: int | None = None) -> None:
        self.button(button, "press", source, ttl_ms)

    def release(self, button: str, source: str = "automation", ttl_ms: int | None = None) -> None:
        self.button(button, "release", source, ttl_ms)

    def button(self, button: str, action: str, source: str = "automation", ttl_ms: int | None = None) -> None:
        payload = {"source": source, "button": button, "action": action}
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("button", payload)

    def set_axis(self, axis: str, value: int, source: str = "automation", ttl_ms: int | None = None) -> None:
        payload = {"source": source, "axis": axis, "value": value}
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("set_axis", payload)

    def set_trigger(self, trigger: str, value: int, source: str = "automation", ttl_ms: int | None = None) -> None:
        payload = {"source": source, "trigger": trigger, "value": value}
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("set_trigger", payload)

    def set_state(self, state: dict[str, Any], source: str = "automation", ttl_ms: int | None = None) -> None:
        payload: dict[str, Any] = {"source": source, "state": state}
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("set_state", payload)

    def heartbeat(self, source: str = "automation", ttl_ms: int | None = None) -> None:
        payload: dict[str, Any] = {"source": source}
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("heartbeat", payload)


class JsonFileTransport:
    """Test/demo transport; it records requests and returns canned responses."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self.responses = responses or [{"ok": True, "payload": {}}]

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(message)
        return self.responses[min(len(self.requests) - 1, len(self.responses) - 1)]

    def close(self) -> None:
        pass

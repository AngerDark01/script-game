"""Small language-neutral client for VirtualGamepadHost's JSON-lines pipe."""

from __future__ import annotations

import json
import ctypes
import os
import threading
import time
from ctypes import wintypes
from typing import Any, Callable, Protocol


PIPE_PATH = r"\\.\pipe\AutoModules.VirtualGamepad.v1"


class VirtualGamepadError(RuntimeError):
    """The host rejected a request or could not be reached."""


class _LinePipe(Protocol):
    """The small text-stream surface the JSON-lines protocol requires."""

    def write(self, value: str) -> int: ...

    def flush(self) -> None: ...

    def readline(self) -> str: ...

    def close(self) -> None: ...


class _WindowsNamedPipe:
    """UTF-8 JSON-lines transport backed by Win32 named-pipe handles.

    The C runtime file layer used by ``open(r"\\\\.\\pipe\\...", "r+")``
    rejects a duplex named-pipe handle with ``EINVAL`` on this runtime.  Using
    the native APIs is also compatible with the Host's byte-transmission mode.
    """

    _GENERIC_READ = 0x80000000
    _GENERIC_WRITE = 0x40000000
    _OPEN_EXISTING = 3
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _ERROR_BROKEN_PIPE = 109
    _ERROR_OPERATION_ABORTED = 995
    _NMPWAIT_NOWAIT = 1
    _THREAD_TERMINATE = 0x0001
    _CLOSE_WAIT_SECONDS = 0.05
    _CANCEL_RETRY_SECONDS = 0.02

    def __init__(self, pipe_path: str) -> None:
        if os.name != "nt":
            raise OSError("Windows named pipes are unavailable on this platform")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        kernel32.WaitNamedPipeW.restype = wintypes.BOOL
        kernel32.WriteFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        kernel32.WriteFile.restype = wintypes.BOOL
        kernel32.ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        kernel32.ReadFile.restype = wintypes.BOOL
        kernel32.GetCurrentThreadId.argtypes = []
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenThread.restype = wintypes.HANDLE
        kernel32.CancelSynchronousIo.argtypes = [wintypes.HANDLE]
        kernel32.CancelSynchronousIo.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32 = kernel32
        self._io_gate = threading.Lock()
        self._io_idle = threading.Event()
        self._io_idle.set()
        self._io_thread_id: int | None = None
        self._closed = False
        self._closer: threading.Thread | None = None
        # Do not let CreateFileW block an elevated UI or automation worker.
        # NMPWAIT_NOWAIT is one millisecond; zero would instead mean that the
        # pipe's default wait timeout should be used.
        if not kernel32.WaitNamedPipeW(pipe_path, self._NMPWAIT_NOWAIT):
            error = ctypes.get_last_error()
            raise OSError(error, ctypes.FormatError(error), pipe_path)
        self._handle = kernel32.CreateFileW(
            pipe_path,
            self._GENERIC_READ | self._GENERIC_WRITE,
            0,
            None,
            self._OPEN_EXISTING,
            0,
            None,
        )
        if self._handle == self._INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            raise OSError(error, ctypes.FormatError(error), pipe_path)
        self._read_buffer = bytearray()

    def write(self, value: str) -> int:
        data = value.encode("utf-8")
        offset = 0
        while offset < len(data):
            chunk = data[offset:]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            handle, thread_id = self._begin_synchronous_io()
            try:
                succeeded = self._kernel32.WriteFile(handle, buffer, len(chunk), ctypes.byref(written), None)
                error = ctypes.get_last_error() if not succeeded else None
            finally:
                self._finish_synchronous_io(thread_id)
            if not succeeded:
                self._raise_last_error(error)
            if written.value == 0:
                raise OSError("WriteFile wrote no bytes to the named pipe")
            offset += written.value
        return len(value)

    def flush(self) -> None:
        # WriteFile delivers this short request to the connected server; a
        # FlushFileBuffers call can block while the server is reading it.
        return None

    def readline(self) -> str:
        while True:
            newline = self._read_buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._read_buffer[: newline + 1])
                del self._read_buffer[: newline + 1]
                return line.decode("utf-8")

            buffer = ctypes.create_string_buffer(4096)
            received = wintypes.DWORD()
            handle, thread_id = self._begin_synchronous_io()
            try:
                succeeded = self._kernel32.ReadFile(handle, buffer, len(buffer), ctypes.byref(received), None)
                error = ctypes.get_last_error() if not succeeded else None
            finally:
                self._finish_synchronous_io(thread_id)
            if not succeeded:
                if error in (self._ERROR_BROKEN_PIPE, self._ERROR_OPERATION_ABORTED):
                    return ""
                self._raise_last_error(error)
            if received.value == 0:
                return ""
            self._read_buffer.extend(buffer.raw[: received.value])

    def close(self) -> None:
        with self._io_gate:
            if self._closed:
                return
            self._closed = True
            handle = self._handle

        if handle is None:
            return

        # Closing a handle concurrently with a synchronous ReadFile/WriteFile
        # is not a defined cancellation mechanism.  First target the owning
        # OS thread with CancelSynchronousIo, then close only after it exits.
        self._cancel_synchronous_io()
        if self._io_idle.wait(self._CLOSE_WAIT_SECONDS):
            self._close_handle()
            return

        # Cancellation is normally immediate.  If Windows is still finishing
        # an I/O request, return promptly without an unsafe concurrent close;
        # this daemon reaper closes the handle once that request has returned.
        closer = threading.Thread(target=self._close_when_idle, name="VirtualGamepadPipeCloser", daemon=True)
        self._closer = closer
        closer.start()

    def _begin_synchronous_io(self) -> tuple[int, int]:
        with self._io_gate:
            if self._closed or self._handle is None:
                raise OSError(self._ERROR_OPERATION_ABORTED, "The named pipe is closed.")
            thread_id = int(self._kernel32.GetCurrentThreadId())
            self._io_thread_id = thread_id
            self._io_idle.clear()
            return self._handle, thread_id

    def _finish_synchronous_io(self, thread_id: int) -> None:
        with self._io_gate:
            if self._io_thread_id == thread_id:
                self._io_thread_id = None
                self._io_idle.set()

    def _cancel_synchronous_io(self) -> None:
        with self._io_gate:
            thread_id = self._io_thread_id
        if thread_id is None:
            return

        thread_handle = self._kernel32.OpenThread(self._THREAD_TERMINATE, False, thread_id)
        if not thread_handle:
            # The target I/O may already have completed between the snapshot
            # and OpenThread.  _io_idle then permits the normal close path.
            return
        try:
            self._kernel32.CancelSynchronousIo(thread_handle)
        finally:
            self._kernel32.CloseHandle(thread_handle)

    def _close_when_idle(self) -> None:
        # There is a narrow interval after _begin_synchronous_io marks the
        # owner but before ReadFile/WriteFile enters the kernel.  A first
        # CancelSynchronousIo in that interval has no target.  Keep retrying
        # until the active I/O returns; never silently strand this handle.
        while not self._io_idle.wait(self._CANCEL_RETRY_SECONDS):
            self._cancel_synchronous_io()
        self._close_handle()

    def _close_handle(self) -> None:
        with self._io_gate:
            handle = self._handle
            self._handle = None
        if handle is not None:
            self._kernel32.CloseHandle(handle)

    def _raise_last_error(self, error: int | None = None) -> None:
        code = ctypes.get_last_error() if error is None else error
        raise OSError(code, ctypes.FormatError(code))


def _open_named_pipe(pipe_path: str) -> _LinePipe:
    if os.name == "nt":
        return _WindowsNamedPipe(pipe_path)
    return open(pipe_path, "r+", encoding="utf-8", newline="\n")


class VirtualGamepadClient:
    def __init__(
        self,
        pipe_path: str = PIPE_PATH,
        transport: Any | None = None,
        pipe_opener: Callable[[str], _LinePipe] | None = None,
    ) -> None:
        self.pipe_path = pipe_path
        self._transport = transport
        self._pipe: _LinePipe | None = None
        self._pipe_opener = pipe_opener or _open_named_pipe
        self._request_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._sequence = 0
        self._connection_epoch = 0

    def connect(self, timeout: float = 5.0) -> None:
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        if self._transport is not None:
            return
        with self._state_lock:
            if self._pipe is not None:
                return
            connection_epoch = self._connection_epoch

        deadline = time.monotonic() + timeout
        last_error: OSError | None = None
        while True:
            try:
                opened_pipe = self._pipe_opener(self.pipe_path)
            except OSError as exc:
                last_error = exc
            else:
                with self._state_lock:
                    if connection_epoch == self._connection_epoch and self._pipe is None:
                        self._pipe = opened_pipe
                        return
                    connected = self._pipe is not None
                opened_pipe.close()
                if connected:
                    return
                raise VirtualGamepadError("Connection was closed while opening the host pipe.")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.05, remaining))

        raise VirtualGamepadError(f"Unable to connect to host pipe {self.pipe_path}: {last_error}")

    def close(self) -> None:
        # State ownership is deliberately separate from request serialization:
        # close() must be able to cancel a request waiting for a host response.
        with self._state_lock:
            pipe = self._pipe
            self._pipe = None
            self._connection_epoch += 1
        if pipe is not None:
            pipe.close()
        close = getattr(self._transport, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> "VirtualGamepadClient":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def request(self, message_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._request_lock:
            self._sequence += 1
            message = {"id": str(self._sequence), "type": message_type, "payload": payload or {}}
            response = self._request_unlocked(message)
        if not response.get("ok", False):
            error = response.get("error") or {}
            raise VirtualGamepadError(f"{error.get('code', 'host_error')}: {error.get('message', response)}")
        return response.get("payload") or {}

    def _request_unlocked(self, message: dict[str, Any]) -> dict[str, Any]:
        if self._transport is not None:
            return self._transport.request(message)
        with self._state_lock:
            pipe = self._pipe
        if pipe is None:
            raise VirtualGamepadError("Client is not connected.")
        try:
            pipe.write(json.dumps(message, separators=(",", ":")) + "\n")
            pipe.flush()
            line = pipe.readline()
        except OSError as exc:
            raise VirtualGamepadError(f"Host pipe I/O failed: {exc}") from exc
        if not line:
            raise VirtualGamepadError("Host closed the pipe.")
        with self._state_lock:
            if self._pipe is not pipe:
                raise VirtualGamepadError("Host closed the pipe.")
        return json.loads(line)

    def hello(self) -> dict[str, Any]:
        return self.request("hello")

    def status(self) -> dict[str, Any]:
        return self.request("get_status")

    def get_config(self, controller: int = 1) -> dict[str, Any]:
        return self.request("get_config", {"controller": controller} if controller != 1 else {})

    def set_config(self, config: dict[str, Any], controller: int = 1) -> None:
        payload = dict(config)
        if controller != 1:
            payload["controller"] = controller
        self.request("set_config", payload)

    def state(self, controller: int = 1) -> dict[str, Any]:
        payload = {"controller": controller} if controller != 1 else {}
        return self.request("get_state", payload)

    @staticmethod
    def _lifecycle_payload(
        controller: int,
        *,
        source: str | None = None,
        sequence: int | None = None,
    ) -> dict[str, Any]:
        if (source is None) != (sequence is None):
            raise ValueError("Lifecycle source and sequence must be supplied together.")
        if source is not None and not source.strip():
            raise ValueError("Lifecycle source must be non-empty.")
        if sequence is not None and sequence < 0:
            raise ValueError("Lifecycle sequence must be non-negative.")
        payload: dict[str, Any] = {"controller": controller} if controller != 1 else {}
        if source is not None:
            payload["source"] = source
            payload["sequence"] = sequence
        return payload

    def start(self, controller: int = 1, *, source: str | None = None, sequence: int | None = None) -> None:
        self.request("start", self._lifecycle_payload(controller, source=source, sequence=sequence))

    def pause(self, controller: int = 1, *, source: str | None = None, sequence: int | None = None) -> None:
        self.request("pause", self._lifecycle_payload(controller, source=source, sequence=sequence))

    def reset(self, controller: int = 1, *, source: str | None = None, sequence: int | None = None) -> None:
        self.request("reset", self._lifecycle_payload(controller, source=source, sequence=sequence))

    def emergency_reset(self) -> None:
        self.request("emergency_reset")

    def press(self, button: str, source: str = "automation", ttl_ms: int | None = None, controller: int = 1) -> None:
        self.button(button, "press", source, ttl_ms, controller=controller)

    def release(self, button: str, source: str = "automation", ttl_ms: int | None = None, controller: int = 1) -> None:
        self.button(button, "release", source, ttl_ms, controller=controller)

    def button(self, button: str, action: str, source: str = "automation", ttl_ms: int | None = None, controller: int = 1) -> None:
        payload = {"source": source, "button": button, "action": action}
        if controller != 1:
            payload["controller"] = controller
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("button", payload)

    def set_axis(self, axis: str, value: int, source: str = "automation", ttl_ms: int | None = None, controller: int = 1) -> None:
        payload = {"source": source, "axis": axis, "value": value}
        if controller != 1:
            payload["controller"] = controller
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("set_axis", payload)

    def set_trigger(self, trigger: str, value: int, source: str = "automation", ttl_ms: int | None = None, controller: int = 1) -> None:
        payload = {"source": source, "trigger": trigger, "value": value}
        if controller != 1:
            payload["controller"] = controller
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("set_trigger", payload)

    def set_state(self, state: dict[str, Any], source: str = "automation", ttl_ms: int | None = None, controller: int = 1) -> None:
        payload: dict[str, Any] = {"source": source, "state": state}
        if controller != 1:
            payload["controller"] = controller
        if ttl_ms is not None:
            payload["ttlMs"] = ttl_ms
        self.request("set_state", payload)

    def heartbeat(self, source: str = "automation", ttl_ms: int | None = None, controller: int = 1) -> None:
        payload: dict[str, Any] = {"source": source}
        if controller != 1:
            payload["controller"] = controller
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

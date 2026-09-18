import ctypes
import os
import threading
import uuid
from ctypes import wintypes

from auto_modules.adapters.virtual_gamepad import JsonFileTransport, VirtualGamepadClient, VirtualGamepadError


class _LinePipe:
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, value: str) -> int:
        self.writes.append(value)
        return len(value)

    def flush(self) -> None:
        pass

    def readline(self) -> str:
        return '{"id":"1","ok":true,"payload":{"connected":true}}\n'

    def close(self) -> None:
        pass


class _BlockingLinePipe(_LinePipe):
    def __init__(self) -> None:
        super().__init__()
        self.read_started = threading.Event()
        self.release_read = threading.Event()

    def readline(self) -> str:
        self.read_started.set()
        # A bounded wait prevents a failed regression test from leaving a
        # non-daemon worker thread behind forever.
        self.release_read.wait(timeout=2)
        return ""

    def close(self) -> None:
        self.release_read.set()


class _WithholdingNamedPipeServer:
    """A tiny byte-mode Windows pipe that reads one request and never replies."""

    _PIPE_ACCESS_DUPLEX = 0x00000003
    _PIPE_TYPE_BYTE = 0x00000000
    _PIPE_READMODE_BYTE = 0x00000000
    _PIPE_NOWAIT = 0x00000001
    _ERROR_PIPE_CONNECTED = 535
    _ERROR_PIPE_LISTENING = 536
    _ERROR_NO_DATA = 232
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    def __init__(self) -> None:
        self.pipe_path = rf"\\.\pipe\AutoModules.VirtualGamepad.PythonTests.{uuid.uuid4().hex}"
        self.ready = threading.Event()
        self.request_received = threading.Event()
        self.stop_requested = threading.Event()
        self.release_response = threading.Event()
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name="WithholdingNamedPipeServer", daemon=True)

    def start(self) -> bool:
        if os.name != "nt":
            return False
        self._thread.start()
        return self.ready.wait(timeout=1) and self.error is None

    def stop(self) -> None:
        self.stop_requested.set()
        self.release_response.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateNamedPipeW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
        ]
        kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
        kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        kernel32.ConnectNamedPipe.restype = wintypes.BOOL
        kernel32.ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        kernel32.ReadFile.restype = wintypes.BOOL
        kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
        kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateNamedPipeW(
            self.pipe_path,
            self._PIPE_ACCESS_DUPLEX,
            self._PIPE_TYPE_BYTE | self._PIPE_READMODE_BYTE | self._PIPE_NOWAIT,
            1,
            4096,
            4096,
            0,
            None,
        )
        connected = False
        if handle == self._INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            self.error = OSError(error, ctypes.FormatError(error), self.pipe_path)
            self.ready.set()
            return

        self.ready.set()
        try:
            while not self.stop_requested.is_set():
                if kernel32.ConnectNamedPipe(handle, None):
                    connected = True
                    break
                error = ctypes.get_last_error()
                if error == self._ERROR_PIPE_CONNECTED:
                    connected = True
                    break
                if error in (self._ERROR_PIPE_LISTENING, self._ERROR_NO_DATA):
                    self.stop_requested.wait(timeout=0.01)
                    continue
                raise OSError(error, ctypes.FormatError(error), self.pipe_path)

            buffer = ctypes.create_string_buffer(4096)
            while connected and not self.stop_requested.is_set():
                received = wintypes.DWORD()
                if kernel32.ReadFile(handle, buffer, len(buffer), ctypes.byref(received), None):
                    if received.value:
                        self.request_received.set()
                        break
                    continue
                error = ctypes.get_last_error()
                if error == self._ERROR_NO_DATA:
                    self.stop_requested.wait(timeout=0.01)
                    continue
                raise OSError(error, ctypes.FormatError(error), self.pipe_path)

            # Leave the connected client waiting for a response until teardown.
            while connected and not self.release_response.wait(timeout=0.01):
                if self.stop_requested.is_set():
                    break
        except BaseException as exc:
            self.error = exc
        finally:
            if connected:
                kernel32.DisconnectNamedPipe(handle)
            kernel32.CloseHandle(handle)


def test_connect_uses_a_pipe_opener_for_a_real_line_transport():
    pipe = _LinePipe()
    opened: list[str] = []
    client = VirtualGamepadClient(
        pipe_path=r"\\.\pipe\test",
        pipe_opener=lambda path: opened.append(path) or pipe,
    )

    client.connect()
    assert client.status() == {"connected": True}
    assert opened == [r"\\.\pipe\test"]
    assert '"type":"get_status"' in pipe.writes[0]


def test_connect_attempts_the_injected_opener_once_with_zero_timeout():
    pipe = _LinePipe()
    client = VirtualGamepadClient(
        pipe_path=r"\\.\pipe\test",
        pipe_opener=lambda path: pipe,
    )

    client.connect(timeout=0)

    assert client.status() == {"connected": True}


def test_close_unblocks_a_pending_response_read_without_waiting_for_request_lock():
    pipe = _BlockingLinePipe()
    client = VirtualGamepadClient(
        pipe_path=r"\\.\pipe\test",
        pipe_opener=lambda path: pipe,
    )
    client.connect()
    errors: list[Exception] = []

    def request_status() -> None:
        try:
            client.status()
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=request_status, daemon=True)
    try:
        worker.start()
        assert pipe.read_started.wait(timeout=1)

        client.close()
        worker.join(timeout=1)

        assert not worker.is_alive()
        assert len(errors) == 1
        assert isinstance(errors[0], VirtualGamepadError)
        assert "closed the pipe" in str(errors[0])
    finally:
        client.close()
        pipe.release_read.set()
        worker.join(timeout=1)


def test_close_unblocks_a_real_windows_named_pipe_read_and_releases_its_handle():
    if os.name != "nt":
        return

    server = _WithholdingNamedPipeServer()
    if not server.start():
        # The helper is intentionally optional for non-Windows-like runners
        # where a local named pipe cannot be created.
        server.stop()
        return

    client = VirtualGamepadClient(pipe_path=server.pipe_path)
    errors: list[Exception] = []

    def request_status() -> None:
        try:
            client.status()
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=request_status, daemon=True)
    native_pipe = None
    try:
        client.connect(timeout=1)
        native_pipe = client._pipe
        assert native_pipe is not None

        worker.start()
        assert server.request_received.wait(timeout=1)

        client.close()
        worker.join(timeout=2)

        assert not worker.is_alive()
        assert len(errors) == 1
        assert isinstance(errors[0], VirtualGamepadError)
        assert "closed the pipe" in str(errors[0])
        assert native_pipe._io_idle.wait(timeout=1)
        closer = native_pipe._closer
        if closer is not None:
            closer.join(timeout=1)
        assert native_pipe._handle is None
        assert closer is None or not closer.is_alive()
        assert server.error is None
    finally:
        client.close()
        server.stop()
        worker.join(timeout=1)


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


def test_lifecycle_commands_encode_optional_source_and_sequence():
    transport = JsonFileTransport()
    client = VirtualGamepadClient(transport=transport)

    client.start()
    client.start(controller=2, source="virtual-gamepad-page:test", sequence=41)
    client.pause(controller=2, source="virtual-gamepad-page:test", sequence=42)
    client.reset(controller=2, source="virtual-gamepad-page:test", sequence=43)

    assert transport.requests[0]["payload"] == {}
    assert transport.requests[1]["payload"] == {
        "controller": 2,
        "source": "virtual-gamepad-page:test",
        "sequence": 41,
    }
    assert transport.requests[2]["payload"]["sequence"] == 42
    assert transport.requests[3]["payload"]["sequence"] == 43


def test_errors_are_exposed_as_virtual_gamepad_errors():
    transport = JsonFileTransport([{"ok": False, "error": {"code": "invalid_argument", "message": "bad"}}])
    client = VirtualGamepadClient(transport=transport)

    try:
        client.start()
    except Exception as exc:
        assert "invalid_argument" in str(exc)
    else:
        raise AssertionError("expected host error")

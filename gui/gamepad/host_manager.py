"""Ownership-aware lifecycle manager for the independent C# gamepad Host.

The workbench deliberately does not embed the ViGEm driver or physical-input
hook.  It either attaches to the already-running Host pipe or starts the Host
from the elevated workbench process, then makes the Host client available to
the embedded page.  A Host started elsewhere is never terminated here.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Callable

from virtual_gamepad.client.python import VirtualGamepadClient


@dataclass(frozen=True)
class HostStartResult:
    """The outcome of a bounded Host readiness attempt."""

    connected: bool
    owns_host: bool
    message: str = ""


@dataclass(frozen=True)
class HostShutdownResult:
    """Safety-cleanup outcome, including whether an owned Host was stopped."""

    succeeded: bool
    errors: tuple[str, ...] = ()
    stopped_owned_host: bool = False


class GamepadHostManager:
    """Start/attach to VirtualGamepadHost and release it safely on exit."""

    PIPE_CONNECT_TIMEOUT_SECONDS = 0.10
    CLEANUP_CONNECT_TIMEOUT_SECONDS = 0.25
    READY_POLL_INTERVAL_SECONDS = 0.05

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any] = VirtualGamepadClient,
        process_factory: Callable[..., Any] = subprocess.Popen,
        host_command_factory: Callable[[], list[str]] | None = None,
        host_working_directory: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client_factory = client_factory
        self._process_factory = process_factory
        self._host_command_factory = host_command_factory or self._default_host_command
        self._host_working_directory = host_working_directory or self._default_host_directory()
        self._clock = clock
        self._sleeper = sleeper
        self._host_process: Any | None = None
        self._owns_host = False
        self._last_start_error = ""

    @property
    def owns_host(self) -> bool:
        return self._owns_host

    @property
    def last_start_error(self) -> str:
        return self._last_start_error

    def create_client(self) -> Any:
        """Return a separate pipe client for the embedded page or automation."""
        return self._client_factory()

    def start(self, timeout: float = 5.0) -> HostStartResult:
        """Attach to an existing Host or launch one and wait a bounded period."""
        timeout = max(0.0, timeout)
        if self._owns_host:
            connected, error = self._probe_host()
            if connected:
                self._last_start_error = ""
                return HostStartResult(True, True, "Using the Host started by this workbench.")
            self._last_start_error = error
            return HostStartResult(False, True, error)

        connected, _error = self._probe_host()
        if connected:
            self._last_start_error = ""
            return HostStartResult(True, False, "Attached to the existing Virtual Gamepad Host.")

        try:
            command = self._host_command_factory()
            if not command:
                raise RuntimeError("Virtual Gamepad Host command is empty.")
            self._host_process = self._process_factory(
                command,
                cwd=str(self._host_working_directory),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=self._detached_creation_flags(),
            )
            self._owns_host = True
        except Exception as exc:
            self._host_process = None
            self._owns_host = False
            self._last_start_error = f"Could not start Virtual Gamepad Host: {exc}"
            return HostStartResult(False, False, self._last_start_error)

        deadline = self._clock() + timeout
        while True:
            connected, error = self._probe_host()
            if connected:
                self._last_start_error = ""
                return HostStartResult(True, True, "Virtual Gamepad Host started.")
            if self._clock() >= deadline:
                self._last_start_error = f"Virtual Gamepad Host did not become ready: {error}"
                self._stop_owned_process()
                return HostStartResult(False, False, self._last_start_error)
            self._sleeper(min(self.READY_POLL_INTERVAL_SECONDS, max(0.0, deadline - self._clock())))

    def shutdown(self) -> HostShutdownResult:
        """Reset/pause both controllers and stop only a Host this manager started.

        Stopping an owned process remains the final safety net if pipe cleanup
        cannot be confirmed: a stopped Host releases its raw-input hook.  An
        externally started Host is never terminated, even after an error.
        """
        errors: list[str] = []
        client: Any | None = None
        try:
            client = self.create_client()
            connect = getattr(client, "connect", None)
            if callable(connect):
                connect(timeout=self.CLEANUP_CONNECT_TIMEOUT_SECONDS)
            for controller in (1, 2):
                for action in ("reset", "pause"):
                    try:
                        method = getattr(client, action)
                        method(controller)
                    except Exception as exc:
                        errors.append(f"Controller {controller} {action} failed: {exc}")
        except Exception as exc:
            errors.append(f"Could not connect cleanup client: {exc}")
        finally:
            if client is not None:
                close = getattr(client, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception as exc:
                        errors.append(f"Could not close cleanup client: {exc}")

        stopped_owned_host = self._stop_owned_process()
        return HostShutdownResult(not errors, tuple(errors), stopped_owned_host)

    def _probe_host(self) -> tuple[bool, str]:
        client: Any | None = None
        try:
            client = self.create_client()
            connect = getattr(client, "connect", None)
            if callable(connect):
                connect(timeout=self.PIPE_CONNECT_TIMEOUT_SECONDS)
            return True, ""
        except Exception as exc:
            return False, str(exc)
        finally:
            if client is not None:
                close = getattr(client, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

    def _stop_owned_process(self) -> bool:
        if not self._owns_host:
            return False
        process = self._host_process
        self._host_process = None
        self._owns_host = False
        if process is None:
            return False
        try:
            process.terminate()
            wait = getattr(process, "wait", None)
            if callable(wait):
                try:
                    wait(timeout=1.0)
                except Exception:
                    kill = getattr(process, "kill", None)
                    if callable(kill):
                        kill()
            return True
        except Exception:
            return False

    @staticmethod
    def _workspace_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @classmethod
    def _default_host_directory(cls) -> Path:
        return cls._workspace_root() / "virtual_gamepad" / "host" / "src" / "VirtualGamepadHost" / "bin" / "Release" / "net8.0-windows"

    @classmethod
    def _default_host_command(cls) -> list[str]:
        host_directory = cls._default_host_directory()
        host_dll = host_directory / "VirtualGamepadHost.dll"
        host_exe = host_directory / "VirtualGamepadHost.exe"
        if host_dll.exists():
            workspace_runtime = cls._workspace_root().parent / "dotnet-sdk2" / "dotnet.exe"
            if workspace_runtime.exists():
                return [str(workspace_runtime), "exec", str(host_dll)]
            discovered_runtime = shutil.which("dotnet")
            if discovered_runtime:
                return [discovered_runtime, "exec", str(host_dll)]
        if host_exe.exists():
            return [str(host_exe)]
        raise FileNotFoundError(f"Compiled Virtual Gamepad Host was not found: {host_dll}")

    @staticmethod
    def _detached_creation_flags() -> int:
        if os.name != "nt":
            return 0
        return getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

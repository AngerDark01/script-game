"""Inert Host doubles for workbench UI tests that do not exercise gamepad I/O."""

from gui.gamepad.host_manager import HostShutdownResult, HostStartResult


class InertGamepadClient:
    def connect(self, timeout: float = 5.0) -> None:
        return None

    def reset(self, _controller: int) -> None:
        return None

    def pause(self, _controller: int) -> None:
        return None

    def close(self) -> None:
        return None


class InertGamepadHostManager:
    """Avoid launching a native Host in unrelated offscreen UI tests."""

    def start(self) -> HostStartResult:
        return HostStartResult(connected=False, owns_host=False, message="Gamepad disabled for this UI test.")

    def create_client(self) -> InertGamepadClient:
        return InertGamepadClient()

    def shutdown(self) -> HostShutdownResult:
        return HostShutdownResult(succeeded=True)

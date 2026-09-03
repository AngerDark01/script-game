from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


BUTTONS = ("A", "B", "X", "Y", "DPadUp", "DPadDown", "DPadLeft", "DPadRight", "Start", "Back", "LeftShoulder", "RightShoulder")
CONTROLS = BUTTONS + ("LeftStick", "RightStick", "LeftTrigger", "RightTrigger")


@dataclass
class StateSnapshot:
    buttons: int = 0
    left_trigger: int = 0
    right_trigger: int = 0
    left_stick_x: int = 0
    left_stick_y: int = 0
    right_stick_x: int = 0
    right_stick_y: int = 0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "StateSnapshot":
        return cls(
            buttons=int(payload.get("buttons", 0)),
            left_trigger=int(payload.get("leftTrigger", payload.get("left_trigger", 0))),
            right_trigger=int(payload.get("rightTrigger", payload.get("right_trigger", 0))),
            left_stick_x=int(payload.get("leftStickX", payload.get("left_stick_x", 0))),
            left_stick_y=int(payload.get("leftStickY", payload.get("left_stick_y", 0))),
            right_stick_x=int(payload.get("rightStickX", payload.get("right_stick_x", 0))),
            right_stick_y=int(payload.get("rightStickY", payload.get("right_stick_y", 0))),
        )

    def is_pressed(self, button: str) -> bool:
        masks = {
            "DPadUp": 0x0001,
            "DPadDown": 0x0002,
            "DPadLeft": 0x0004,
            "DPadRight": 0x0008,
            "Start": 0x0010,
            "Back": 0x0020,
            "LeftShoulder": 0x0100,
            "RightShoulder": 0x0200,
            "A": 0x1000,
            "B": 0x2000,
            "X": 0x4000,
            "Y": 0x8000,
        }
        return bool(self.buttons & masks.get(button, 0))

    def axis(self, control: str) -> tuple[int, int]:
        if control == "LeftStick":
            return self.left_stick_x, self.left_stick_y
        if control == "RightStick":
            return self.right_stick_x, self.right_stick_y
        return (0, 0)


@dataclass
class UiStatus:
    run_state: str = "Disconnected"
    driver_installed: bool = False
    device_connected: bool = False
    message: str = "Not connected"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "UiStatus":
        state = payload.get("runState", payload.get("run_state", "Disconnected"))
        return cls(
            run_state=str(state),
            driver_installed=bool(payload.get("driverInstalled", payload.get("driver_installed", False))),
            device_connected=bool(payload.get("deviceConnected", payload.get("device_connected", False))),
            message=str(payload.get("message", "")),
        )


@dataclass
class BindingProfile:
    bindings: dict[str, list[str]] = field(default_factory=dict)
    start_pause: str = "F8"
    emergency_reset: str = "F9"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "BindingProfile":
        raw = payload.get("bindings", {})
        if isinstance(raw, list):
            converted: dict[str, list[str]] = {}
            for item in raw:
                if isinstance(item, dict) and item.get("target") and item.get("source"):
                    converted.setdefault(str(item["target"]), []).append(str(item["source"]))
            raw = converted
        return cls(
            bindings={str(key): [str(value) for value in values] for key, values in dict(raw).items()},
            start_pause=str(payload.get("startPause", payload.get("start_pause", "F8"))),
            emergency_reset=str(payload.get("emergencyReset", payload.get("emergency_reset", "F9"))),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "bindings": {key: list(values) for key, values in self.bindings.items()},
            "startPause": self.start_pause,
            "emergencyReset": self.emergency_reset,
        }

    def label_for(self, control: str) -> str:
        return ", ".join(self.bindings.get(control, [])) or "Unbound"

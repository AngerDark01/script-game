from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox


@dataclass(frozen=True)
class MappingRuntimeLifecycleTargets:
    parent: object
    app_context: object
    start_button: object
    get_fps: Callable[[], int]
    on_tick: Callable[[], None]


class MappingRuntimeLifecycle:
    """Own mapping capture timer and monitoring command state."""

    def __init__(self, targets: MappingRuntimeLifecycleTargets) -> None:
        self.targets = targets
        self.capture_timer = QTimer()
        self.capture_timer.timeout.connect(targets.on_tick)

    def toggle_monitoring(self) -> None:
        self.targets.app_context.monitoring = not self.targets.app_context.monitoring
        if self.targets.app_context.monitoring:
            if not self._has_capture_config():
                self.targets.app_context.monitoring = False
                QMessageBox.warning(self.targets.parent, "提示", "请先选择一个监控区域或中心点。")
                return
            self.capture_timer.start(1000 // self.targets.get_fps())
            self.targets.start_button.setText("⏸️ 停止监控")
        else:
            self.stop_runtime()

    def stop_runtime(self) -> None:
        self.capture_timer.stop()
        self.targets.app_context.monitoring = False
        self.targets.start_button.setText("▶️ 开始监控")

    def _has_capture_config(self) -> bool:
        return bool(
            self.targets.app_context.monitor_region
            or self.targets.app_context.monitor_logical_center
        )

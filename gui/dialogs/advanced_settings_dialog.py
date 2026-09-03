"""
高级参数调节面板。

本文件保留 dialog shell 和参数应用/保存/加载行为；具体 tab 和控件创建在
`gui.dialogs.advanced_settings.tabs` 中。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFileDialog

from .advanced_settings.file_io import (
    advanced_settings_output_dir,
    format_params_for_display,
    load_params_snapshot,
    save_params_snapshot,
)
from .advanced_settings.params_adapter import (
    apply_loaded_params_to_widgets,
    apply_preset_to_widgets,
    collect_params_from_widgets,
    load_params_to_widgets,
    reset_widgets_to_default,
)
from .advanced_settings.tabs import build_advanced_settings_ui


class AdvancedSettingsDialog(QDialog):
    """Advanced image-processing parameter dialog."""

    apply_params_requested = Signal(dict)

    def __init__(self, parent, current_params):
        super().__init__(parent)
        self.setWindowTitle("高级参数调节")
        self.resize(800, 600)
        self.setSizeGripEnabled(True)

        self.current_params = current_params
        self.recognizer = parent.recognizer if hasattr(parent, "recognizer") else None
        self.stitcher = parent.stitcher if hasattr(parent, "stitcher") else None
        self._direct_runtime_apply_enabled = True

        self.setup_ui()
        self.load_current_params()

    def use_external_apply_handler(self) -> None:
        """Let the owner consume apply requests instead of direct parent mutation."""
        self._direct_runtime_apply_enabled = False

    def setup_ui(self) -> None:
        """Build the dialog UI through the advanced-settings tab module."""
        build_advanced_settings_ui(self)

    def get_params(self) -> dict:
        """Return the last applied parameter snapshot."""
        return self.current_params

    def load_current_params(self) -> None:
        """Load current parameters into the widgets."""
        load_params_to_widgets(self, self.current_params)

    def apply_params(self) -> None:
        """Collect and apply parameters."""
        params = collect_params_from_widgets(self)
        self.apply_params_requested.emit(params)

        if self._direct_runtime_apply_enabled:
            self._apply_params_directly(params)

        self.current_params = params
        print("✅ 参数已应用")

    def _apply_params_directly(self, params: dict) -> None:
        """Compatibility fallback for callers that have not connected the command signal."""
        if self.recognizer:
            self.recognizer.set_params(params)
        else:
            print("⚠️ 警告：无法实时应用参数（未找到识别器实例）")

        if self.stitcher:
            self.stitcher.set_params(params)
        else:
            print("⚠️ 警告：无法实时应用参数（未找到拼接器实例）")

    def reset_to_default(self) -> None:
        """Reset widgets to default parameters."""
        reset_widgets_to_default(self)

    def save_current_params(self) -> None:
        """Save current parameters to a JSON snapshot."""
        if not self.param_name_edit.text().strip():
            self.save_status_label.setText("请输入参数配置名称")
            return

        param_name = self.param_name_edit.text().strip()
        try:
            saved_path = save_params_snapshot(param_name, self.current_params)
            self.save_status_label.setText(f"✅ 参数已保存到 {saved_path}")
        except Exception as exc:
            self.save_status_label.setText(f"❌ 保存失败: {exc}")

    def load_params_from_file(self) -> None:
        """Load parameters from a JSON snapshot chosen by the user."""
        settings_dir = advanced_settings_output_dir()
        settings_dir.mkdir(parents=True, exist_ok=True)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择参数文件",
            str(settings_dir),
            "JSON Files (*.json)",
        )

        if not filename:
            return

        try:
            data = load_params_snapshot(filename)
            params = data["parameters"]
            self.loaded_params_text.setPlainText(format_params_for_display(params))
            self.temp_loaded_params = params
            self.save_status_label.setText(f"已加载参数文件: {filename}")
        except Exception as exc:
            self.loaded_params_text.setPlainText(f"加载失败: {exc}")

    def apply_loaded_params(self) -> None:
        """Write loaded parameters into widgets; applying still requires the apply button."""
        if hasattr(self, "temp_loaded_params"):
            apply_loaded_params_to_widgets(self, self.temp_loaded_params)
            print("✅ 已加载参数，点击应用参数按钮生效")

    def apply_preset(self) -> None:
        """Apply the selected preset to widgets."""
        apply_preset_to_widgets(self, self.preset_combo.currentText())

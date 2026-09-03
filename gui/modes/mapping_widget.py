
import json

from PySide6.QtWidgets import (
    QWidget, QApplication,
    QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt

from ..dialogs.color_picker_dialog import ColorPickerDialog
from ..dialogs.advanced_settings_dialog import AdvancedSettingsDialog
from .mapping.io import (
    MappingConfigRestoreTargets,
    build_mapping_config,
    restore_saved_mapping_config,
    save_mapping_map,
    save_root_config,
)
from .mapping.capture import CaptureSelectionResult, MappingCaptureSelectionController
from .mapping.presentation import update_mapping_displays
from .mapping.params import (
    apply_hsv_toggles,
    apply_merge_weight,
    feature_params_from_widgets,
)
from .mapping.runtime import (
    MappingRuntimeLifecycle,
    MappingRuntimeLifecycleTargets,
    MappingSession,
)
from .mapping.ui import build_mapping_ui

class MappingWidget(QWidget):
    """绘图模式专属控件"""

    def __init__(self, app_context, main_window, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.main_window = main_window

        # 状态变量
        self.capture_selection = MappingCaptureSelectionController(
            self.app_context,
            compute_scale=self._compute_scale,
        )
        self.nav_path = None
        self.map_crop_offset = (0, 0)
        self.monitor_center = None # 物理中心点
        self.last_capture_size = None
        self.last_player_local_pos = None
        self.mapping_session = MappingSession(
            self.app_context,
            get_monitor_center=lambda: self.monitor_center,
            get_last_player_local_pos=lambda: self.last_player_local_pos,
        )

        # UI 组件
        self.setup_ui()
        self.runtime_lifecycle = MappingRuntimeLifecycle(
            MappingRuntimeLifecycleTargets(
                parent=self,
                app_context=self.app_context,
                start_button=self.start_btn,
                get_fps=lambda: self.fps_spin.value(),
                on_tick=self.capture_and_process,
            )
        )
        self.load_saved_params()

    def setup_ui(self):
        """设置界面"""
        build_mapping_ui(self)

    def _compute_scale(self):
        screen = QApplication.primaryScreen()
        return screen.devicePixelRatio(), screen.devicePixelRatio()

    def select_region(self):
        self.capture_selection.start_region_selection(
            lambda result: self._handle_capture_selection_result(result, save=True)
        )

    def on_region_selected(self, x, y, width, height):
        result = self.capture_selection.apply_region_selection(x, y, width, height)
        self._handle_capture_selection_result(result, save=True)

    def select_center_point(self):
        self.capture_selection.start_center_selection(
            lambda result: self._handle_capture_selection_result(result, save=True)
        )

    def on_center_selected(self, x, y):
        result = self.capture_selection.apply_center_selection(x, y, self.size_spin.value())
        self._handle_capture_selection_result(result, save=True)

    def update_capture_size(self, size):
        result = self.capture_selection.update_capture_size(size)
        if result is not None:
            self._handle_capture_selection_result(result, save=True)

    def _handle_capture_selection_result(self, result: CaptureSelectionResult, *, save: bool):
        self.monitor_center = result.physical_center
        self.region_label.setText(result.label_text)
        self.start_btn.setEnabled(True)
        self.color_picker_btn.setEnabled(True)
        if save:
            self.save_config()

    def open_color_picker(self):
        if not self.app_context.monitor_region and not self.app_context.monitor_logical_center:
            return

        if self.app_context.monitor_logical_center:
            screenshot = self.app_context.screen_capture.capture_square(*self.monitor_center, self.app_context.monitor_size)
        else:
            region = self.app_context.monitor_region
            screenshot = self.app_context.screen_capture.capture(region['left'], region['top'], region['width'], region['height'])
        
        dialog = ColorPickerDialog(screenshot, self, recognizer_params=self.app_context.recognizer.get_params())
        if dialog.exec():
            result = dialog.get_result()
            if result['wall_hsv']:
                min_hsv, max_hsv = result['wall_hsv']
                self.app_context.recognizer.wall_hsv_min = min_hsv
                self.app_context.recognizer.wall_hsv_max = max_hsv
            if result['player_hsv']:
                min_hsv, max_hsv = result['player_hsv']
                self.app_context.recognizer.player_hsv_min = min_hsv
                self.app_context.recognizer.player_hsv_max = max_hsv
            self.save_config()

    def toggle_monitoring(self):
        self.runtime_lifecycle.toggle_monitoring()

    def stop_runtime(self) -> None:
        """Stop mapping capture without depending on the monitoring toggle state."""
        self.runtime_lifecycle.stop_runtime()

    def capture_and_process(self):
        if not self.app_context.monitoring: return

        result = self.mapping_session.tick()
        if result is None:
            return
        self.last_capture_size = result.capture_size
        self.last_player_local_pos = result.player_pos

        self.update_displays(
            result.current_image,
            result.combined_mask,
            player_pos=result.player_pos,
            capture_size=result.capture_size,
        )
        self.update_statistics()

    def update_displays(self, current_img, combined_mask, player_pos=None, capture_size=None):
        result = update_mapping_displays(
            capture_label=self.capture_label,
            global_map_widget=self.global_map_widget,
            stitcher=self.app_context.stitcher,
            current_img=current_img,
            nav_path=self.nav_path,
            current_crop_offset=self.map_crop_offset,
            last_capture_size=self.last_capture_size,
            last_player_local_pos=self.last_player_local_pos,
            player_pos=player_pos,
            capture_size=capture_size,
        )
        self.map_crop_offset = result.map_crop_offset


    def on_map_click(self, x, y):
        crop_x1, crop_y1 = self.map_crop_offset
        start_pos = (self.app_context.stitcher.current_x, self.app_context.stitcher.current_y)
        end_pos = (x + crop_x1, y + crop_y1)
        self.nav_path = self.app_context.path_finder.find_path(
            self.app_context.stitcher.wall_layer,
            start_pos,
            end_pos,
            explored_map=self.app_context.stitcher.explored_map,
        )
        self.update_displays(None, None)


    def update_statistics(self):
        stats = self.app_context.stitcher.get_statistics()
        self.stats_text.setText(f"总帧数: {stats['total_frames']}\n成功匹配: {stats['successful_matches']}")

    def update_hsv_params(self):
        apply_hsv_toggles(self.app_context.recognizer, self.wall_check, self.fog_check)

    def update_feature_params(self):
        params = feature_params_from_widgets(
            clahe_check=self.clahe_check,
            deepen_check=self.deepen_check,
            wall_weight_spin=self.wall_weight_spin,
            edge_weight_spin=self.edge_weight_spin,
            gray_weight_spin=self.gray_weight_spin,
            canny_low_spin=self.canny_low_spin,
            canny_high_spin=self.canny_high_spin,
        )
        self.app_context.recognizer.set_params(params)
        self.save_config()

    def update_merge_params(self):
        apply_merge_weight(self.app_context.stitcher, self.weight_spin)

    def update_geometry_params(self):
        if self._stitcher_is_empty():
            self.app_context.stitcher.reinitialize_canvas(
                canvas_size=self.canvas_size_spin.value(),
                draw_scale=self.draw_scale_spin.value(),
                wall_close_kernel_size=self.wall_close_kernel_spin.value(),
            )
        self.app_context.recognizer.set_params({
            "player_clear_radius": self.player_clear_radius_spin.value(),
        })
        self.app_context.stitcher.set_params({
            "wall_close_kernel_size": self.wall_close_kernel_spin.value(),
        })
        self.save_config()

    def open_advanced_settings(self):
        current_params = self.app_context.recognizer.get_params()
        stitcher_params = self.app_context.stitcher.get_params()
        current_params.update(stitcher_params)

        dialog = AdvancedSettingsDialog(self, current_params)
        dialog.apply_params_requested.connect(
            lambda params: self._apply_advanced_settings_params(params, save=False)
        )
        dialog.use_external_apply_handler()
        if dialog.exec():
            new_params = dialog.get_params()
            self._apply_advanced_settings_params(new_params, save=True)

    def _apply_advanced_settings_params(self, params: dict, *, save: bool = True):
        self.app_context.recognizer.set_params(params)
        self.app_context.stitcher.set_params(params)
        if save:
            self.save_config()

    def reset_map(self):
        self.app_context.stitcher.reinitialize_canvas(
            canvas_size=self.canvas_size_spin.value(),
            draw_scale=self.draw_scale_spin.value(),
            wall_close_kernel_size=self.wall_close_kernel_spin.value(),
        )
        self.app_context.recognizer.set_params({
            "player_clear_radius": self.player_clear_radius_spin.value(),
        })
        self.app_context.tracker.reset()
        self.global_map_widget.set_image(None)
        self.stats_text.clear()
        self.save_config()

    def save_map(self):
        map_name, ok = QInputDialog.getText(self, '保存地图', '请输入地图名称:')
        if not ok or not map_name: return

        config_data = self._build_mapping_config_with_ui_overrides(include_draw_scale=True)
        save_mapping_map(__file__, map_name, stitcher=self.app_context.stitcher, config_data=config_data)

        QMessageBox.information(self, "成功", f"地图 '{map_name}' 已保存!")

    def save_config(self):
        config = self._build_mapping_config_with_ui_overrides()
        save_root_config(__file__, config)

    def load_saved_params(self):
        try:
            restore_saved_mapping_config(
                __file__,
                app_context=self.app_context,
                capture_selection=self.capture_selection,
                handle_capture_selection_result=self._handle_capture_selection_result,
                stitcher_is_empty=self._stitcher_is_empty,
                targets=MappingConfigRestoreTargets(
                    size_spin=self.size_spin,
                    fps_spin=self.fps_spin,
                    clahe_check=self.clahe_check,
                    deepen_check=self.deepen_check,
                    wall_weight_spin=self.wall_weight_spin,
                    edge_weight_spin=self.edge_weight_spin,
                    gray_weight_spin=self.gray_weight_spin,
                    canny_low_spin=self.canny_low_spin,
                    canny_high_spin=self.canny_high_spin,
                    weight_spin=self.weight_spin,
                    draw_scale_spin=self.draw_scale_spin,
                    canvas_size_spin=self.canvas_size_spin,
                    player_clear_radius_spin=self.player_clear_radius_spin,
                    wall_close_kernel_spin=self.wall_close_kernel_spin,
                ),
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"配置文件 'config.json' 加载失败或格式错误: {e}")

    def _build_mapping_config_with_ui_overrides(self, *, include_draw_scale: bool = False) -> dict:
        config = build_mapping_config(
            self.app_context,
            self.fps_spin.value(),
            include_draw_scale=include_draw_scale,
        )
        stitcher_params = dict(config.get("stitcher_params", {}))
        stitcher_params["draw_scale"] = float(self.draw_scale_spin.value())
        stitcher_params["canvas_size"] = int(self.canvas_size_spin.value())
        stitcher_params["wall_close_kernel_size"] = int(self.wall_close_kernel_spin.value())
        config["stitcher_params"] = stitcher_params
        if include_draw_scale:
            config["draw_scale"] = float(self.draw_scale_spin.value())

        recognizer_params = dict(config.get("recognizer_params", {}))
        recognizer_params["player_clear_radius"] = int(self.player_clear_radius_spin.value())
        config["recognizer_params"] = recognizer_params
        return config

    def _stitcher_is_empty(self) -> bool:
        return int(self.app_context.stitcher.stats.get("total_frames", 0)) == 0

    def update_topmost(self):
        if self.topmost_check.isChecked():
            self.main_window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.main_window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.main_window.show()

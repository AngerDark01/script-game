"""Page lifecycle and preview methods extracted from the experiment page."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLabel

from auto_modules.ui.widgets.aspect_preview import AspectPreviewLabel
from .presenter import frame_pixmap


class Poe2PageLifecycleMixin:
    def save_map(self) -> None:
        self._logger.info("step=test_page.save_clicked")
        snapshot = self.service.snapshot() or self._snapshot
        if snapshot is None:
            self._show_error(RuntimeError("请先获取当前地图"))
            return
        try:
            path = self.archive.save(snapshot)
        except Exception as exc:
            self._logger.exception("step=test_page.save_failed error=%s", exc)
            self._show_error(exc)
            return
        self.archive_label.setText(f"已保存地图：{path}")
        self.error_label.clear()
        self._logger.info("step=test_page.save_success path=%s", path)

    def refresh_preview(self) -> None:
        self._logger.info("step=test_page.preview_clicked")
        if self.preview_provider is None:
            self._clear_preview("截图预览后端未注入")
            return
        try:
            frame = self.preview_provider(self.monitor_config)
            if frame is None:
                raise RuntimeError("截图后端返回空帧")
            self._render_preview(frame)
        except Exception as exc:
            self._logger.exception("step=test_page.preview_failed error=%s", exc)
            self._clear_preview(str(exc))
            return
        self.error_label.clear()
        self._logger.info("step=test_page.preview_success")

    def _render_preview(self, frame, *, combined=None, processed=None) -> None:
        self._set_preview(self.frame_preview, frame)
        if self.recognizer is None:
            self._clear_label(self.processed_preview, "未注入预处理器")
            self._clear_label(self.feature_preview, "未注入特征提取器")
            return
        if processed is None:
            processed = self.recognizer.preprocess_image(frame)
        if combined is None:
            marker = getattr(getattr(self.monitor_config, "binding", None), "player_marker_position", None)
            options = (
                {"exclude_player": False, "exclude_dynamic": False}
                if self._dual_preview_active
                else {}
            )
            combined = self.recognizer.extract_combined(frame, player_pos=marker, **options)
        feature = combined[0] if isinstance(combined, (tuple, list)) else combined
        self._set_preview(self.processed_preview, processed)
        self._set_preview(self.feature_preview, feature)

    def _set_preview(self, label: QLabel, frame) -> None:
        pixmap = frame_pixmap(frame)
        if pixmap.isNull():
            self._clear_label(label, "本帧无画面")
            return
        label.set_source_pixmap(pixmap)

    @staticmethod
    def _clear_label(label: QLabel, message: str) -> None:
        if isinstance(label, AspectPreviewLabel):
            label.clear_source(message)
            return
        label.clear()
        label.setText(message)

    def _clear_preview(self, error: str) -> None:
        self._clear_label(self.frame_preview, "本帧无画面")
        self._clear_label(self.processed_preview, "本帧无画面")
        self._clear_label(self.feature_preview, "本帧无特征")
        self._show_error(RuntimeError(error))

    def start_preview(self) -> None:
        self.stop_dual_motion()
        self.preview_timer.setInterval(self._preview_interval())
        self.preview_timer.start()
        self.refresh_preview()
        self.start_preview_button.setEnabled(False)
        self.stop_preview_button.setEnabled(True)
        self._logger.info("step=test_page.preview_started interval_ms=%s", self.preview_timer.interval())

    def stop_preview(self) -> None:
        self.preview_timer.stop()
        self.start_preview_button.setEnabled(True)
        self.stop_preview_button.setEnabled(False)
        self._logger.info("step=test_page.preview_stopped")

    def reset_session(self) -> None:
        self._logger.info("step=test_page.reset")
        self.stop_program_move_probe()
        self.stop_dual_motion()
        self.stop_preview()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self.service.reset()
        self._snapshot = None
        self._clear_map_state()
        self.archive_label.setText("尚未保存地图")
        self._clear_preview("尚未截图")
        self.error_label.clear()
        self._render_state("未初始化")

    def _clear_map_state(self) -> None:
        self._invalidate_dual_motion_session()
        self.stop_dual_motion()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self._sync_follow_role_choices({})
        self._snapshot = None
        self._player_position = None
        self._terrain_base_pixmap = None
        self._hybrid_experiment = None
        self._last_hybrid_state = None
        self.map_widget.set_image(None)
        self.metadata_label.setText("尚未获取地图")
        self.player_position_label.setText("人物位置：未读取")
        self.save_button.setEnabled(False)
        self.hybrid_status_label.setText("混合定位：未启动")
        self.hybrid_position_label.setText("实时位置：暂无")
        self.single_frame_status_label.setText("首帧定位：未启动")
        self.dual_first_frame_status_label.setText("双人首帧：未启动")
        self.dual_motion_status_label.setText("双人实时：未启动")
        self.follow_status_label.setText("跟随实验：先启动双人实时定位，再选择 P1/P2 和点击地图")
        self._last_dual_first_frame_result = None
        self._dual_initial_frame = None
        self._dual_initial_candidates = ()
        self._dual_last_recovery_at_ms = None
        self._dual_first_frame_read_count = 0
        self._dual_preview_active = False
        self._follow_output_not_before_ms = None
        self._follow_output_delay_last_log_at_ms = None
        self.multiframe_status_label.setText("多帧定位：未启动")
        self.multiframe_position_label.setText("多帧位置：暂无")
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory.clear()
        self._multiframe_trajectory_version = 0
        self.multiframe_panel.set_submap(None)
        self.multiframe_panel.set_archive_available(False)

    def _invalidate_dual_motion_session(self) -> None:
        """Cancel delayed dual-worker recovery for the current page/map state."""
        self._dual_motion_session_token += 1
        self._dual_motion_restart_pending = None

    def _render_state(self, text: str) -> None:
        value = getattr(getattr(self.service, "state", "new"), "value", getattr(self.service, "state", "new"))
        has_snapshot = self.service.snapshot() is not None or self._snapshot is not None
        self.status_label.setText(f"状态：{text}（会话：{value}）")
        self.capture_button.setEnabled(value in {"ready_to_capture", "captured"})
        self.save_button.setEnabled(has_snapshot)
        self.refresh_preview_button.setEnabled(self.preview_provider is not None)
        self.start_hybrid_button.setEnabled(
            has_snapshot
            and self.hybrid_localization_factory is not None
            and not self.hybrid_timer.isActive()
        )
        self.start_single_frame_button.setEnabled(
            has_snapshot
            and self.hybrid_localization_factory is not None
            and not self.hybrid_timer.isActive()
        )
        self.dual_first_frame_button.setEnabled(
            has_snapshot and self.preview_provider is not None and self.recognizer is not None
        )
        self.start_dual_motion_button.setEnabled(
            has_snapshot and self.preview_provider is not None and self.recognizer is not None
            and not self._dual_motion_timer.isActive()
        )
        self.start_multiframe_button.setEnabled(
            has_snapshot
            and self.multiframe_localization_factory is not None
            and not self._multiframe_timer.isActive()
        )
        self.localization_control_dialog.set_ready(
            has_snapshot and self.multiframe_localization_factory is not None
        )

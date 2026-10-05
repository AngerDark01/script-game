"""Detached PoE2 screenshot monitor and comparison-sample browser."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import cv2
from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
)

from auto_modules.features.poe2.live_terrain import (
    CaptureEvidence,
    CaptureSampleArchive,
    get_terrain_logger,
)
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.ui.modes.mapping.map_renderer import render_global_map_pixmap
from auto_modules.ui.widgets.scalable_map import ScalableMapWidget
from auto_modules.ui.widgets.aspect_preview import AspectPreviewLabel

from .presenter import frame_pixmap, present_localization_overlay, present_snapshot


class Poe2CaptureMonitorWindow(QDialog):
    """Continuously display and explicitly archive synchronized visual evidence."""

    def __init__(
        self,
        *,
        preview_provider: Callable[[Any], Any],
        recognizer: Any,
        monitor_config_provider: Callable[[], Any],
        terrain_snapshot_provider: Callable[[], Any],
        sample_archive: CaptureSampleArchive,
        stitching_session: Any,
        stitching_archive: Any,
        player_position_provider: Callable[[], Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PoE2 截图监控与样本对比")
        self.resize(1500, 920)
        self.preview_provider = preview_provider
        self.recognizer = recognizer
        self.monitor_config_provider = monitor_config_provider
        self.terrain_snapshot_provider = terrain_snapshot_provider
        self.sample_archive = sample_archive
        self.stitching_session = stitching_session
        self.stitching_archive = stitching_archive
        self.player_position_provider = player_position_provider
        self._logger = get_terrain_logger()
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.refresh_frame)
        self.current_evidence: CaptureEvidence | None = None
        self._current_terrain = None
        self._stitching_snapshot = self.stitching_session.snapshot()
        self.history_records = ()
        self.history_index = -1
        self._build_ui()
        self.reload_history()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.start_button = QPushButton("开始监控")
        self.stop_button = QPushButton("停止监控")
        self.refresh_button = QPushButton("手动刷新")
        self.save_button = QPushButton("保存当前对比样本")
        self.open_folder_button = QPushButton("打开样本目录")
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.refresh_button.clicked.connect(self.refresh_frame)
        self.save_button.clicked.connect(self.save_current_sample)
        self.open_folder_button.clicked.connect(self.open_samples_folder)
        for button in (
            self.start_button,
            self.stop_button,
            self.refresh_button,
            self.save_button,
            self.open_folder_button,
        ):
            controls.addWidget(button)
        controls.addStretch()
        root.addLayout(controls)

        self.status_label = QLabel("状态：尚未截图")
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.hybrid_status_label = QLabel("混合定位：未启动")
        self.hybrid_status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        root.addWidget(self.error_label)
        root.addWidget(self.hybrid_status_label)

        self.workspace_splitter = QSplitter(Qt.Horizontal, self)
        previews = QGroupBox("当前同步证据")
        preview_grid = QGridLayout(previews)
        self.raw_preview = self._preview_label("尚未截图")
        self.processed_preview = self._preview_label("尚未生成预处理画面")
        self.feature_preview = self._preview_label("尚未生成匹配特征")
        self.wall_preview = self._preview_label("尚未生成墙体层")
        self.terrain_preview = self._preview_label("尚未获取当前地形")
        for index, (title, label) in enumerate(
            (
                ("原始小地图截图", self.raw_preview),
                ("预处理画面", self.processed_preview),
                ("匹配特征", self.feature_preview),
                ("实际落图墙体", self.wall_preview),
                ("当前完整地形", self.terrain_preview),
            )
        ):
            row, column = divmod(index, 3)
            panel = QVBoxLayout()
            title_label = QLabel(title)
            title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            panel.addWidget(title_label)
            panel.addWidget(label, 1)
            preview_grid.addLayout(panel, row, column)
        self.workspace_splitter.addWidget(previews)

        stitching = QGroupBox("启动局部地图拼接")
        stitching_root = QVBoxLayout(stitching)
        stitching_controls = QHBoxLayout()
        self.start_stitching_button = QPushButton("开始绘图")
        self.pause_stitching_button = QPushButton("暂停绘图")
        self.reset_stitching_button = QPushButton("重置地图")
        self.save_stitching_button = QPushButton("保存拼图实验")
        self.open_stitching_folder_button = QPushButton("打开拼图目录")
        self.start_stitching_button.clicked.connect(self.start_stitching)
        self.pause_stitching_button.clicked.connect(self.pause_stitching)
        self.reset_stitching_button.clicked.connect(self.reset_stitching)
        self.save_stitching_button.clicked.connect(self.save_stitching_session)
        self.open_stitching_folder_button.clicked.connect(self.open_stitching_folder)
        for button in (
            self.start_stitching_button,
            self.pause_stitching_button,
            self.reset_stitching_button,
            self.save_stitching_button,
            self.open_stitching_folder_button,
        ):
            stitching_controls.addWidget(button)
        stitching_controls.addStretch()
        stitching_root.addLayout(stitching_controls)
        self.stitching_map = ScalableMapWidget(self)
        self.stitching_map.setMinimumSize(560, 420)
        stitching_root.addWidget(self.stitching_map, 1)
        self.stitching_status_label = QLabel("绘图：未开始")
        self.stitching_status_label.setWordWrap(True)
        stitching_root.addWidget(self.stitching_status_label)
        self.workspace_splitter.addWidget(stitching)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setStretchFactor(0, 2)
        self.workspace_splitter.setStretchFactor(1, 3)

        history = QGroupBox("历史样本对比")
        history_root = QVBoxLayout(history)
        history_controls = QHBoxLayout()
        self.previous_button = QPushButton("上一个样本")
        self.next_button = QPushButton("下一个样本")
        self.layer_combo = QComboBox()
        for text, layer in (
            ("原始截图", "raw"),
            ("预处理画面", "processed"),
            ("匹配特征", "feature"),
            ("墙体层", "wall_mask"),
            ("迷雾层", "fog_mask"),
            ("灰度匹配层", "raw_gray"),
            ("完整地形", "terrain"),
        ):
            self.layer_combo.addItem(text, layer)
        self.history_label = QLabel("尚无历史样本")
        self.previous_button.clicked.connect(self.show_previous_sample)
        self.next_button.clicked.connect(self.show_next_sample)
        self.layer_combo.currentIndexChanged.connect(self._render_history)
        history_controls.addWidget(self.previous_button)
        history_controls.addWidget(self.next_button)
        history_controls.addWidget(QLabel("对比图层"))
        history_controls.addWidget(self.layer_combo)
        history_controls.addWidget(self.history_label, 1)
        history_root.addLayout(history_controls)
        history_views = QHBoxLayout()
        previous_panel = QVBoxLayout()
        previous_panel.addWidget(QLabel("上一个样本"))
        self.history_previous_preview = self._preview_label("没有更早样本")
        previous_panel.addWidget(self.history_previous_preview)
        current_panel = QVBoxLayout()
        current_panel.addWidget(QLabel("当前样本"))
        self.history_current_preview = self._preview_label("尚无当前样本")
        current_panel.addWidget(self.history_current_preview)
        history_views.addLayout(previous_panel)
        history_views.addLayout(current_panel)
        history_root.addLayout(history_views)
        self.content_splitter = QSplitter(Qt.Vertical, self)
        self.content_splitter.addWidget(self.workspace_splitter)
        self.content_splitter.addWidget(history)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setStretchFactor(0, 4)
        self.content_splitter.setStretchFactor(1, 2)
        self.content_splitter.setSizes([650, 260])
        root.addWidget(self.content_splitter, 1)

        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self._render_stitching(self._stitching_snapshot)

    @staticmethod
    def _preview_label(message: str) -> QLabel:
        label = AspectPreviewLabel(message)
        label.setMinimumSize(240, 160)
        label.setStyleSheet("background: #101318; border: 1px solid #39414d;")
        return label

    def _config(self):
        config = self.monitor_config_provider()
        if config is None:
            raise RuntimeError("PoE2 监控配置不可用")
        return config

    @staticmethod
    def _config_payload(config: Any) -> dict[str, Any]:
        serializer = getattr(config, "as_dict", None)
        if callable(serializer):
            payload = serializer()
        elif isinstance(config, Mapping):
            payload = config
        else:
            payload = vars(config)
        if not isinstance(payload, Mapping):
            raise TypeError("monitor config serializer must return a mapping")
        return {str(key): value for key, value in payload.items()}

    def _interval(self) -> int:
        try:
            return max(20, int(getattr(self._config(), "sample_interval_ms", 100)))
        except Exception:
            return 100

    @staticmethod
    def _terrain_orientation(config: Any) -> TerrainOrientation:
        del config
        return TerrainOrientation()

    def start_monitoring(self) -> None:
        self.preview_timer.setInterval(self._interval())
        self.preview_timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.refresh_frame()

    def handle_hybrid_state(self, state: Any, *, read_count: int = 0) -> None:
        mode = getattr(getattr(state, "mode", "unknown"), "value", getattr(state, "mode", "unknown"))
        source = str(getattr(state, "source", "failed"))
        confidence = float(getattr(state, "confidence", 0.0))
        position = getattr(state, "position", None)
        self.hybrid_status_label.setText(
            f"混合定位：{mode} | {source} | 置信度 {confidence:.3f} | "
            f"读取 {int(read_count)} 次 | 位置 {position if position is not None else '本帧失败'}"
        )
        terrain = self.terrain_snapshot_provider()
        if terrain is None:
            return
        base = present_snapshot(terrain, self._terrain_orientation(self._config())).pixmap
        overlay = present_localization_overlay(base, state)
        self._set_pixmap(self.terrain_preview, overlay, "地形预览不可用")

    def stop_monitoring(self) -> None:
        self.preview_timer.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def refresh_frame(self) -> None:
        try:
            config = self._config()
            raw = self.preview_provider(config)
            if raw is None:
                raise RuntimeError("截图后端返回空帧")
            processed = self.recognizer.preprocess_image(raw)
            marker = getattr(getattr(config, "binding", None), "player_marker_position", None)
            combined = self.recognizer.extract_combined(raw, player_pos=marker)
            if isinstance(combined, tuple):
                feature = combined[0]
                wall_mask = combined[1] if len(combined) > 1 else feature
                fog_mask = combined[2] if len(combined) > 2 else None
            else:
                feature = combined
                wall_mask = feature
                fog_mask = None
            raw_gray_provider = getattr(self.recognizer, "get_raw_gray", None)
            raw_gray = raw_gray_provider(raw) if callable(raw_gray_provider) else None
            evidence = CaptureEvidence(
                captured_at=datetime.now(timezone.utc).isoformat(),
                raw=raw,
                processed=processed,
                feature=feature,
                monitor_config=self._config_payload(config),
                wall_mask=wall_mask,
                fog_mask=fog_mask,
                raw_gray=raw_gray,
            )
            terrain = self.terrain_snapshot_provider()
            orientation = self._terrain_orientation(config)
        except Exception as exc:
            self._logger.exception("step=capture_monitor.refresh_failed error=%s", exc)
            self._invalidate_current_frame(str(exc))
            return
        self.current_evidence = evidence
        self._current_terrain = terrain
        self._set_frame(self.raw_preview, evidence.raw)
        self._set_frame(self.processed_preview, evidence.processed)
        self._set_frame(self.feature_preview, evidence.feature)
        self._set_frame(self.wall_preview, evidence.wall_mask)
        if terrain is None:
            self._clear_label(self.terrain_preview, "当前没有地形快照")
        else:
            pixmap = present_snapshot(terrain, orientation).pixmap
            self._set_pixmap(self.terrain_preview, pixmap, "地形预览不可用")
        self.status_label.setText(f"状态：当前帧有效（{evidence.captured_at}）")
        self.error_label.clear()
        self.save_button.setEnabled(True)
        if self.stitching_session.state == "running":
            try:
                stitching = self.stitching_session.consume(evidence)
                self._render_stitching(stitching)
                self._logger.debug(
                    "step=stitching.frame total=%s quality=%.3f position=%s",
                    stitching.statistics.get("total_frames", 0),
                    float(stitching.statistics.get("match_quality", 0.0)),
                    stitching.current_position,
                )
            except Exception as exc:
                self._logger.exception("step=stitching.frame_failed error=%s", exc)
                self._render_stitching(self.stitching_session.pause())
                self.error_label.setText(f"错误：拼图帧处理失败：{exc}")

    def start_stitching(self) -> None:
        try:
            config = self._config()
            params = getattr(config, "stitcher_params", None)
            if params is None:
                params = self._config_payload(config).get("stitcher_params", {})
            configure = getattr(self.stitching_session, "configure", None)
            if callable(configure):
                configure(params)
        except Exception as exc:
            self._logger.exception("step=stitching.configure_failed error=%s", exc)
            self.error_label.setText(f"错误：应用拼接参数失败：{exc}")
            return
        self._logger.info("step=stitching.start params=%s", dict(params))
        self._render_stitching(self.stitching_session.start())
        if self.preview_timer.isActive():
            self.refresh_frame()
        else:
            self.start_monitoring()

    def pause_stitching(self) -> None:
        self._logger.info("step=stitching.pause")
        self._render_stitching(self.stitching_session.pause())

    def reset_stitching(self) -> None:
        self._logger.info("step=stitching.reset")
        self._render_stitching(self.stitching_session.reset())
        self.status_label.setText("状态：拼接地图已重置")
        self.error_label.clear()

    def save_stitching_session(self):
        if self.current_evidence is None:
            self.error_label.setText("错误：当前没有可关联的有效截图")
            return None
        snapshot = self.stitching_session.snapshot()
        try:
            path = self.stitching_archive.save(
                snapshot,
                self.current_evidence,
                terrain=self._current_terrain,
            )
        except Exception as exc:
            self._logger.exception("step=stitching.save_failed error=%s", exc)
            self.error_label.setText(f"错误：保存拼图实验失败：{exc}")
            return None
        self.error_label.clear()
        self.status_label.setText(f"状态：拼图实验已保存到 {path}")
        self._logger.info("step=stitching.save_success path=%s", path)
        return path

    def _render_stitching(self, snapshot) -> None:
        self._stitching_snapshot = snapshot
        if snapshot.current_position is None or snapshot.map_image is None:
            self.stitching_map.set_image(None)
        else:
            pixmap = render_global_map_pixmap(
                global_map=snapshot.map_image,
                crop_x1=snapshot.map_origin[0],
                crop_y1=snapshot.map_origin[1],
                nav_path=snapshot.trajectory,
                current_position=snapshot.current_position,
                draw_scale=snapshot.draw_scale,
                player_pos=snapshot.player_position,
                capture_size=snapshot.capture_size,
            )
            self.stitching_map.set_image(pixmap)
        stats = dict(snapshot.statistics)
        state_text = {"idle": "未开始", "running": "绘图中", "paused": "已暂停"}.get(
            snapshot.state,
            snapshot.state,
        )
        self.stitching_status_label.setText(
            f"绘图：{state_text} | 帧 {int(stats.get('total_frames', 0))} | "
            f"成功 {int(stats.get('successful_matches', 0))} | "
            f"失败 {int(stats.get('failed_matches', 0))} | "
            f"质量 {float(stats.get('match_quality', 0.0)):.2f} | "
            f"匹配率 {float(stats.get('match_rate', 0.0)):.1f}% | "
            f"关键帧 {int(stats.get('keyframe_switches', 0))} | "
            f"低质量跳过 {int(stats.get('low_quality_skipped', 0))} | "
            f"位置 {snapshot.current_position or '-'}"
        )
        self.start_stitching_button.setEnabled(snapshot.state != "running")
        self.pause_stitching_button.setEnabled(snapshot.state == "running")
        self.reset_stitching_button.setEnabled(bool(snapshot.trajectory))
        self.save_stitching_button.setEnabled(
            bool(snapshot.trajectory) and self.current_evidence is not None
        )

    def save_current_sample(self):
        if self.current_evidence is None:
            self.error_label.setText("错误：当前没有可保存的有效截图")
            return None
        try:
            record = self.sample_archive.save(
                self.current_evidence,
                terrain=self._current_terrain,
                player_position=(
                    self.player_position_provider()
                    if self.player_position_provider is not None
                    else None
                ),
            )
        except Exception as exc:
            self.error_label.setText(f"错误：保存对比样本失败：{exc}")
            return None
        self.error_label.clear()
        self.status_label.setText(f"状态：样本已保存到 {record.path}")
        self.reload_history(select_path=record.path)
        return record

    def reload_history(self, *, select_path: Path | None = None) -> None:
        self.history_records = self.sample_archive.list_samples()
        if not self.history_records:
            self.history_index = -1
        elif select_path is not None:
            resolved = Path(select_path).resolve()
            self.history_index = next(
                (index for index, item in enumerate(self.history_records) if item.path == resolved),
                len(self.history_records) - 1,
            )
        elif self.history_index < 0:
            self.history_index = len(self.history_records) - 1
        else:
            self.history_index = min(self.history_index, len(self.history_records) - 1)
        self._render_history()

    def show_previous_sample(self) -> None:
        if self.history_index > 0:
            self.history_index -= 1
        self._render_history()

    def show_next_sample(self) -> None:
        if 0 <= self.history_index < len(self.history_records) - 1:
            self.history_index += 1
        self._render_history()

    def _render_history(self, *_args) -> None:
        count = len(self.history_records)
        valid = 0 <= self.history_index < count
        self.previous_button.setEnabled(valid and self.history_index > 0)
        self.next_button.setEnabled(valid and self.history_index < count - 1)
        if not valid:
            self.history_label.setText("尚无历史样本")
            self._clear_label(self.history_previous_preview, "没有更早样本")
            self._clear_label(self.history_current_preview, "尚无当前样本")
            return
        current = self.history_records[self.history_index]
        previous = self.history_records[self.history_index - 1] if self.history_index > 0 else None
        self.history_label.setText(
            f"{self.history_index + 1}/{count} · {current.path.name}"
        )
        layer = self.layer_combo.currentData() or "raw"
        self._set_record_layer(self.history_current_preview, current, layer, "当前样本缺少此图层")
        if previous is None:
            self._clear_label(self.history_previous_preview, "没有更早样本")
        else:
            self._set_record_layer(
                self.history_previous_preview,
                previous,
                layer,
                "上一个样本缺少此图层",
            )

    def _set_record_layer(self, label: QLabel, record, layer: str, missing: str) -> None:
        path = record.images.get(layer)
        if path is None:
            self._clear_label(label, missing)
            return
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None:
            self._clear_label(label, "图像读取失败")
            return
        self._set_frame(label, image)

    def _set_frame(self, label: QLabel, frame: Any) -> None:
        self._set_pixmap(label, frame_pixmap(frame), "图像不可用")

    @staticmethod
    def _set_pixmap(label: QLabel, pixmap, missing: str) -> None:
        if pixmap is None or pixmap.isNull():
            Poe2CaptureMonitorWindow._clear_label(label, missing)
            return
        label.set_source_pixmap(pixmap)

    @staticmethod
    def _clear_label(label: QLabel, message: str) -> None:
        if isinstance(label, AspectPreviewLabel):
            label.clear_source(message)
            return
        label.clear()
        label.setText(message)

    def _invalidate_current_frame(self, error: str) -> None:
        self.current_evidence = None
        self._current_terrain = None
        self.save_button.setEnabled(False)
        self._clear_label(self.raw_preview, "本帧无画面")
        self._clear_label(self.processed_preview, "本帧无画面")
        self._clear_label(self.feature_preview, "本帧无特征")
        self._clear_label(self.wall_preview, "本帧无墙体层")
        self._clear_label(self.terrain_preview, "本帧未关联地形")
        self.status_label.setText("状态：当前帧无效")
        self.error_label.setText(f"错误：{error}")

    def open_samples_folder(self) -> None:
        self.sample_archive.root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.sample_archive.root)))

    def open_stitching_folder(self) -> None:
        self.stitching_archive.root.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.stitching_archive.root)))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self.preview_timer.isActive():
            self.start_monitoring()

    def closeEvent(self, event) -> None:
        self.stop_monitoring()
        self.pause_stitching()
        self.current_evidence = None
        self._current_terrain = None
        self.save_button.setEnabled(False)
        super().closeEvent(event)


__all__ = ["Poe2CaptureMonitorWindow"]

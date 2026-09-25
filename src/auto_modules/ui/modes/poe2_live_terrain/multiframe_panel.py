"""Presentation-only controls and diagnostics for the PoE2 multiframe experiment."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QCheckBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class Poe2MultiframePanel(QGroupBox):
    start_requested = Signal()
    stop_requested = Signal()
    reset_requested = Signal()
    save_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("多帧全局定位实验", parent)
        layout = QVBoxLayout(self)

        strategy_row = QHBoxLayout()
        self.strategy_a_check = QCheckBox("方案 A：局部拼图")
        self.strategy_b_check = QCheckBox("方案 B：多帧候选")
        self.strategy_a_check.setChecked(True)
        self.strategy_b_check.setChecked(True)
        strategy_row.addWidget(self.strategy_a_check)
        strategy_row.addWidget(self.strategy_b_check)
        strategy_row.addStretch()
        layout.addLayout(strategy_row)

        controls = QHBoxLayout()
        self.start_button = QPushButton("开始")
        self.stop_button = QPushButton("停止")
        self.reset_button = QPushButton("重置")
        self.save_button = QPushButton("保存实验")
        self.start_button.clicked.connect(self.start_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.save_button.clicked.connect(self.save_requested.emit)
        for button in (self.start_button, self.stop_button, self.reset_button, self.save_button):
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)

        self.status_label = QLabel("多帧定位：未启动")
        self.status_label.setWordWrap(True)
        self.position_label = QLabel("多帧位置：暂无")
        self.diagnostics_label = QLabel("关键帧 0 | 候选 0 | 内存读取 0 | 后台注册 否")
        self.diagnostics_label.setWordWrap(True)
        self.candidate_label = QLabel("A/B 结果：暂无")
        self.candidate_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addWidget(self.position_label)
        layout.addWidget(self.diagnostics_label)
        layout.addWidget(self.candidate_label)

        self.submap_preview = QLabel("局部拼图：暂无")
        self.submap_preview.setAlignment(Qt.AlignCenter)
        self.submap_preview.setMinimumSize(180, 120)
        self.submap_preview.setStyleSheet("border: 1px solid #3c4654; background: #11151a;")
        layout.addWidget(self.submap_preview)
        self.save_button.setEnabled(False)
        self.set_running(False)

    def selected_strategies(self) -> tuple[bool, bool]:
        return self.strategy_a_check.isChecked(), self.strategy_b_check.isChecked()

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.strategy_a_check.setEnabled(not running)
        self.strategy_b_check.setEnabled(not running)

    def set_archive_available(self, available: bool) -> None:
        self.save_button.setEnabled(bool(available))

    def set_state(
        self,
        *,
        status: str,
        evidence_version: int,
        recovery_revision: int,
        reason: str,
        position,
        keyframes: int = 0,
        candidates: int = 0,
        memory_reads: int = 0,
        registration_pending: bool = False,
        strategy_a_status: str | None = None,
        best_candidate=None,
        evidence_bytes: int = 0,
        tick_elapsed_ms: float = 0.0,
        registration_elapsed_ms: float = 0.0,
    ) -> None:
        self.status_label.setText(
            f"多帧定位：{status} | evidence {int(evidence_version)} | "
            f"恢复版本 {int(recovery_revision)} | {reason}"
        )
        self.position_label.setText(f"多帧位置：{position if position is not None else '暂无'}")
        self.diagnostics_label.setText(
            f"关键帧 {int(keyframes)} | 候选 {int(candidates)} | "
            f"证据 {float(evidence_bytes) / (1024 * 1024):.1f} MB | 内存读取 {int(memory_reads)} | "
            f"帧耗时 {float(tick_elapsed_ms):.1f} ms | 注册 {float(registration_elapsed_ms):.1f} ms | "
            f"后台注册 {'是' if registration_pending else '否'}"
        )
        candidate_text = f"方案 A：{strategy_a_status or '未运行'}"
        if best_candidate is not None:
            transform = getattr(best_candidate, "transform", None)
            candidate_text += (
                f" | 方案 B：{float(getattr(transform, 'angle_degrees', 0.0)):.1f}°"
                f" / {'镜像' if bool(getattr(transform, 'reflect_horizontal', False)) else '原向'}"
                f" / {float(getattr(transform, 'scale', 1.0)):.3f}"
                f" / 分数 {float(getattr(best_candidate, 'score', 0.0)):.3f}"
            )
        else:
            candidate_text += " | 方案 B：暂无候选"
        self.candidate_label.setText(candidate_text)

    def set_submap(self, mask) -> None:
        if mask is None:
            self.submap_preview.setText("局部拼图：暂无")
            self.submap_preview.setPixmap(QPixmap())
            return
        array = np.asarray(mask, dtype=np.uint8)
        if array.ndim != 2 or array.size == 0:
            self.submap_preview.setText("局部拼图：暂无")
            self.submap_preview.setPixmap(QPixmap())
            return
        image = QImage(array.data, array.shape[1], array.shape[0], array.strides[0], QImage.Format_Grayscale8).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.submap_preview.size(), Qt.KeepAspectRatio, Qt.FastTransformation
        )
        self.submap_preview.setPixmap(pixmap)


__all__ = ["Poe2MultiframePanel"]

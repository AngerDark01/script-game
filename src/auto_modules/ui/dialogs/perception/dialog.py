from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
)

from auto_modules.core.perception import CoordinateSpace, FrameContext, PerceptionPipeline
from auto_modules.core.perception.builtins import create_default_algorithm_registry
from auto_modules.core.perception.profile_store import load_target_profile, save_target_profile
from auto_modules.core.perception.profiles import AlgorithmProfile, TargetProfile
from .parameter_form import ParameterEditor
from .preview import DetectionPreview


class PerceptionWorkbenchDialog(QDialog):
    """Standalone profile editor and screenshot test bench for reusable detectors."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Perception Workbench")
        self.resize(1120, 720)
        self.setMinimumSize(760, 520)
        self.registry = create_default_algorithm_registry()
        self.pipeline = PerceptionPipeline(self.registry)
        self.profile_path: Path | None = None
        self._image: np.ndarray | None = None
        self._algorithm_profiles: list[AlgorithmProfile] = []
        self._selected_algorithm_row = -1
        self._editor_updating = False
        self._build_ui()
        self._set_default_profile()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Perception Workbench")
        title.setProperty("role", "empty-title")
        header.addWidget(title)
        header.addWidget(QLabel("Reusable algorithm profiles and full-screen test runs"), 1)
        self.status_label = QLabel("Ready")
        self.status_label.setProperty("role", "muted")
        header.addWidget(self.status_label)
        root.addLayout(header)

        profile_box = QGroupBox("Profile")
        profile_form = QFormLayout(profile_box)
        self.game_edit = QLineEdit()
        self.scene_edit = QLineEdit()
        self.target_edit = QLineEdit()
        profile_form.addRow("Game", self.game_edit)
        profile_form.addRow("Scene", self.scene_edit)
        profile_form.addRow("Target type", self.target_edit)
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setDecimals(3)
        self.confidence_spin.setValue(0.5)
        profile_form.addRow("Minimum confidence", self.confidence_spin)
        self.confirmation_spin = QSpinBox()
        self.confirmation_spin.setRange(1, 120)
        profile_form.addRow("Confirmation frames", self.confirmation_spin)
        self.merge_radius_spin = QDoubleSpinBox()
        self.merge_radius_spin.setRange(0.0, 500.0)
        self.merge_radius_spin.setDecimals(1)
        self.merge_radius_spin.setValue(12.0)
        profile_form.addRow("Fusion radius (px)", self.merge_radius_spin)
        self.space_combo = QComboBox()
        for space in CoordinateSpace:
            self.space_combo.addItem(space.value, space)
        self.space_combo.setCurrentIndex(self.space_combo.findData(CoordinateSpace.FULL_SCREEN.value))
        profile_form.addRow("Input coordinate space", self.space_combo)
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["confidence", "nearest", "first"])
        profile_form.addRow("Selection strategy", self.strategy_combo)
        root.addWidget(profile_box)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_algorithm_panel())
        splitter.addWidget(self._build_editor_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.setSizes([245, 310, 520])
        root.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.load_image_button = QPushButton("Load image")
        self.load_image_button.clicked.connect(self.load_image)
        self.run_button = QPushButton("Run detection")
        self.run_button.setProperty("role", "primary")
        self.run_button.clicked.connect(self.run_detection)
        self.load_profile_button = QPushButton("Open profile")
        self.load_profile_button.clicked.connect(self.open_profile)
        self.save_profile_button = QPushButton("Save profile")
        self.save_profile_button.setProperty("role", "success")
        self.save_profile_button.clicked.connect(self.save_profile)
        actions.addWidget(self.load_image_button)
        actions.addWidget(self.run_button)
        actions.addStretch(1)
        actions.addWidget(self.load_profile_button)
        actions.addWidget(self.save_profile_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        actions.addWidget(close_button)
        root.addLayout(actions)

    def _build_algorithm_panel(self) -> QWidget:
        panel = QGroupBox("Algorithm instances")
        layout = QVBoxLayout(panel)
        self.algorithm_combo = QComboBox()
        for descriptor in self.registry.descriptors():
            label = descriptor.display_name
            if descriptor.status != "available":
                label += f" ({descriptor.status})"
            self.algorithm_combo.addItem(label, descriptor.algorithm_id)
        layout.addWidget(self.algorithm_combo)
        self.algorithm_list = QListWidget()
        self.algorithm_list.currentRowChanged.connect(self._algorithm_selected)
        self.algorithm_list.itemChanged.connect(self._algorithm_item_changed)
        layout.addWidget(self.algorithm_list, 1)
        buttons = QHBoxLayout()
        add = QPushButton("Add")
        add.clicked.connect(self.add_algorithm)
        remove = QPushButton("Remove")
        remove.clicked.connect(self.remove_algorithm)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout.addLayout(buttons)
        return panel

    def _build_editor_panel(self) -> QWidget:
        panel = QGroupBox("Selected algorithm")
        layout = QVBoxLayout(panel)
        self.algorithm_title = QLabel("No algorithm selected")
        self.algorithm_title.setProperty("role", "empty-title")
        self.algorithm_description = QLabel("")
        self.algorithm_description.setWordWrap(True)
        self.algorithm_description.setProperty("role", "muted")
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.0, 10.0)
        self.weight_spin.setDecimals(2)
        self.weight_spin.setSingleStep(0.1)
        self.weight_spin.setValue(1.0)
        layout.addWidget(self.algorithm_title)
        layout.addWidget(self.algorithm_description)
        weight_form = QFormLayout()
        weight_form.setContentsMargins(0, 0, 0, 0)
        weight_form.addRow("Instance weight", self.weight_spin)
        layout.addLayout(weight_form)
        self.parameter_editor = ParameterEditor()
        layout.addWidget(self.parameter_editor)
        layout.addStretch(1)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QGroupBox("Test preview")
        layout = QVBoxLayout(panel)
        self.preview = DetectionPreview()
        layout.addWidget(self.preview, 1)
        self.result_label = QLabel("No detections")
        self.result_label.setWordWrap(True)
        self.result_label.setProperty("role", "muted")
        layout.addWidget(self.result_label)
        return panel

    def _set_default_profile(self) -> None:
        self.game_edit.setText("default_game")
        self.scene_edit.setText("default_scene")
        self.target_edit.setText("target")
        self.confirmation_spin.setValue(1)
        self.merge_radius_spin.setValue(12.0)
        self._algorithm_profiles = [
            AlgorithmProfile("color-1", "color", parameters={"target_type": "target"}),
        ]
        self._refresh_algorithm_list(select_row=0)

    def add_algorithm(self) -> None:
        algorithm_id = self.algorithm_combo.currentData()
        if not algorithm_id:
            return
        instance_id = self._next_instance_id(algorithm_id)
        self._algorithm_profiles.append(AlgorithmProfile(instance_id, algorithm_id))
        self._refresh_algorithm_list(select_row=len(self._algorithm_profiles) - 1)

    def remove_algorithm(self) -> None:
        row = self.algorithm_list.currentRow()
        if row < 0 or row >= len(self._algorithm_profiles):
            return
        self._commit_current_algorithm()
        self._algorithm_profiles.pop(row)
        self._refresh_algorithm_list(select_row=max(0, row - 1))

    def _next_instance_id(self, algorithm_id: str) -> str:
        existing = {profile.instance_id for profile in self._algorithm_profiles}
        suffix = 1
        while f"{algorithm_id}-{suffix}" in existing:
            suffix += 1
        return f"{algorithm_id}-{suffix}"

    def _refresh_algorithm_list(self, select_row: int = -1) -> None:
        self._commit_current_algorithm()
        self._selected_algorithm_row = -1
        self.algorithm_list.blockSignals(True)
        self.algorithm_list.clear()
        for profile in self._algorithm_profiles:
            try:
                descriptor = self.registry.descriptor(profile.algorithm_id)
                label = f"{descriptor.display_name}  -  {profile.instance_id}"
            except KeyError:
                label = f"Unknown  -  {profile.instance_id}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, profile.instance_id)
            item.setCheckState(Qt.CheckState.Checked if profile.enabled else Qt.CheckState.Unchecked)
            self.algorithm_list.addItem(item)
        self.algorithm_list.blockSignals(False)
        if self._algorithm_profiles:
            self.algorithm_list.setCurrentRow(min(max(select_row, 0), len(self._algorithm_profiles) - 1))
        else:
            self._algorithm_selected(-1)

    def _algorithm_selected(self, row: int) -> None:
        self._commit_current_algorithm(self._selected_algorithm_row)
        self._selected_algorithm_row = row
        if row < 0 or row >= len(self._algorithm_profiles):
            self.algorithm_title.setText("No algorithm selected")
            self.algorithm_description.setText("")
            self.parameter_editor.set_descriptor(None)
            return
        profile = self._algorithm_profiles[row]
        try:
            descriptor = self.registry.descriptor(profile.algorithm_id)
        except KeyError:
            self.algorithm_title.setText(f"Unknown algorithm: {profile.algorithm_id}")
            self.algorithm_description.setText("This profile needs an installed algorithm provider.")
            self.parameter_editor.set_descriptor(None)
            return
        self.algorithm_title.setText(f"{descriptor.display_name}  -  {profile.instance_id}")
        self.algorithm_description.setText(descriptor.description)
        self._editor_updating = True
        try:
            self.weight_spin.setValue(profile.weight)
            self.parameter_editor.set_descriptor(descriptor, profile.parameters)
        finally:
            self._editor_updating = False

    def _algorithm_item_changed(self, item: QListWidgetItem) -> None:
        row = self.algorithm_list.row(item)
        if 0 <= row < len(self._algorithm_profiles):
            self._commit_current_algorithm()
            profile = self._algorithm_profiles[row]
            self._algorithm_profiles[row] = AlgorithmProfile(
                profile.instance_id,
                profile.algorithm_id,
                parameters=profile.parameters,
                enabled=item.checkState() == Qt.CheckState.Checked,
                weight=profile.weight,
                metadata=profile.metadata,
            )

    def _commit_current_algorithm(self, row: int | None = None) -> None:
        row = self._selected_algorithm_row if row is None else row
        if row < 0 or row >= len(self._algorithm_profiles) or self._editor_updating:
            return
        profile = self._algorithm_profiles[row]
        parameters = self.parameter_editor.values()
        item = self.algorithm_list.item(row)
        enabled = item is None or item.checkState() == Qt.CheckState.Checked
        self._algorithm_profiles[row] = AlgorithmProfile(
            profile.instance_id,
            profile.algorithm_id,
            parameters=parameters,
            enabled=enabled,
            weight=float(self.weight_spin.value()),
            metadata=profile.metadata,
        )

    def _build_profile(self) -> TargetProfile:
        self._commit_current_algorithm()
        game = self.game_edit.text().strip() or "default_game"
        scene = self.scene_edit.text().strip() or "default_scene"
        target = self.target_edit.text().strip() or "target"
        return TargetProfile(
            game_id=game,
            scene_id=scene,
            target_type=target,
            algorithms=tuple(self._algorithm_profiles),
            min_confidence=float(self.confidence_spin.value()),
            confirmation_frames=int(self.confirmation_spin.value()),
            selection_strategy=self.strategy_combo.currentText(),
            metadata={
                "merge_radius": float(self.merge_radius_spin.value()),
                "coordinate_space": str(self.space_combo.currentData()),
            },
        )

    def load_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load screenshot", "", "Images (*.png *.jpg *.jpeg *.bmp);;All files (*)")
        if not path:
            return
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            QMessageBox.warning(self, "Image", "The selected image could not be read.")
            return
        self._image = image
        self.preview.set_image(_pixmap_from_bgr(image), (image.shape[1], image.shape[0]))
        self.preview.set_detections(())
        self.result_label.setText(f"Loaded {Path(path).name} - {image.shape[1]}x{image.shape[0]}")
        self.status_label.setText("Image loaded")

    def run_detection(self) -> None:
        if self._image is None:
            self.status_label.setText("Load an image first")
            return
        try:
            profile = self._build_profile()
            frame = FrameContext(
                image=self._image,
                captured_at_ms=int(time.time() * 1000),
                source="perception_workbench",
                width=int(self._image.shape[1]),
                height=int(self._image.shape[0]),
                coordinate_space=CoordinateSpace(str(self.space_combo.currentData())),
            )
            result = self.pipeline.run(frame, profile)
        except Exception as exc:
            self.status_label.setText("Run failed")
            QMessageBox.warning(self, "Detection", f"{type(exc).__name__}: {exc}")
            return
        self.preview.set_detections(result.detections)
        summary = [f"{len(result.detections)} fused detection(s)"]
        if result.errors:
            summary.append("Errors: " + "; ".join(result.errors.values()))
        self.result_label.setText(" - ".join(summary))
        self.status_label.setText("Run complete")

    def open_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open perception profile", "", "JSON (*.json);;All files (*)")
        if not path:
            return
        try:
            profile = load_target_profile(path)
        except Exception as exc:
            QMessageBox.warning(self, "Profile", f"Could not open profile: {type(exc).__name__}: {exc}")
            return
        self._load_profile(profile)
        self.profile_path = Path(path)
        self.status_label.setText(f"Opened {Path(path).name}")

    def _load_profile(self, profile: TargetProfile) -> None:
        self._commit_current_algorithm()
        self.game_edit.setText(profile.game_id)
        self.scene_edit.setText(profile.scene_id)
        self.target_edit.setText(profile.target_type)
        self.confidence_spin.setValue(profile.min_confidence)
        self.confirmation_spin.setValue(profile.confirmation_frames)
        self.merge_radius_spin.setValue(float(profile.metadata.get("merge_radius", 12.0)))
        space = profile.metadata.get("coordinate_space", CoordinateSpace.FULL_SCREEN.value)
        try:
            space_value = CoordinateSpace(space)
        except (TypeError, ValueError):
            space_value = CoordinateSpace.FULL_SCREEN
        space_index = self.space_combo.findData(space_value.value)
        self.space_combo.setCurrentIndex(space_index if space_index >= 0 else self.space_combo.findData(CoordinateSpace.FULL_SCREEN))
        index = self.strategy_combo.findText(profile.selection_strategy)
        self.strategy_combo.setCurrentIndex(index if index >= 0 else 0)
        self._algorithm_profiles = list(profile.algorithms)
        self._selected_algorithm_row = -1
        self._refresh_algorithm_list(select_row=0)

    def save_profile(self) -> None:
        self._commit_current_algorithm()
        path = self.profile_path
        if path is None:
            selected, _ = QFileDialog.getSaveFileName(self, "Save perception profile", "perception-profile.json", "JSON (*.json)")
            if not selected:
                return
            path = Path(selected)
        try:
            save_target_profile(path, self._build_profile())
        except Exception as exc:
            QMessageBox.warning(self, "Profile", f"Could not save profile: {type(exc).__name__}: {exc}")
            return
        self.profile_path = path
        self.status_label.setText(f"Saved {path.name}")


def _pixmap_from_bgr(image: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    qimage = QImage(rgb.data, width, height, int(rgb.strides[0]), QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage.copy())

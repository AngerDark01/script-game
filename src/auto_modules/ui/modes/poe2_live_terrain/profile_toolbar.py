"""Local profile selector for the PoE2 monitor workbench."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QPushButton, QComboBox, QWidget

from auto_modules.features.poe2.live_terrain import Poe2MonitorConfig, Poe2MonitorProfileStore


class Poe2ProfileToolbar(QWidget):
    profile_selected = Signal(object)

    def __init__(self, store: Poe2MonitorProfileStore, *, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        layout = QHBoxLayout(self)
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._activate_current)
        layout.addWidget(self.profile_combo, 1)
        self.new_button = QPushButton("新建")
        self.copy_button = QPushButton("复制")
        self.rename_button = QPushButton("重命名")
        self.delete_button = QPushButton("删除")
        for button in (self.new_button, self.copy_button, self.rename_button, self.delete_button):
            layout.addWidget(button)
        self.new_button.clicked.connect(self.create_profile)
        self.copy_button.clicked.connect(self.copy_profile)
        self.rename_button.clicked.connect(self.rename_profile)
        self.delete_button.clicked.connect(self.delete_profile)
        self.refresh()

    def refresh(self, selected_id: str | None = None) -> None:
        profiles = self.store.list_profiles()
        active = selected_id or (self.store.active().profile_id if self.store.active() else None)
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in profiles:
            self.profile_combo.addItem(profile.profile_name, profile.profile_id)
        index = self.profile_combo.findData(active)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        self._update_enabled()

    def current(self) -> Poe2MonitorConfig | None:
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return None
        return self.store.get(str(profile_id))

    def _activate_current(self, _index: int) -> None:
        profile = self.current()
        if profile is None:
            return
        self.store.activate(profile.profile_id)
        self.profile_selected.emit(profile)

    def create_profile(self) -> None:
        name, accepted = QInputDialog.getText(self, "新建配置", "配置名称")
        if accepted and name.strip():
            profile = self.store.create(name.strip(), template=self.current())
            self.refresh(profile.profile_id)
            self.profile_selected.emit(profile)

    def copy_profile(self) -> None:
        current = self.current()
        if current is None:
            return
        name, accepted = QInputDialog.getText(self, "复制配置", "新配置名称", text=f"{current.profile_name} 副本")
        if accepted and name.strip():
            profile = self.store.copy(current.profile_id, name.strip())
            self.refresh(profile.profile_id)
            self.profile_selected.emit(profile)

    def rename_profile(self) -> None:
        current = self.current()
        if current is None:
            return
        name, accepted = QInputDialog.getText(self, "重命名配置", "配置名称", text=current.profile_name)
        if accepted and name.strip():
            profile = self.store.rename(current.profile_id, name.strip())
            self.refresh(profile.profile_id)
            self.profile_selected.emit(profile)

    def delete_profile(self) -> None:
        current = self.current()
        if current is None:
            return
        self.store.delete(current.profile_id)
        profile = self.store.active()
        self.refresh(profile.profile_id if profile else None)
        if profile is not None:
            self.profile_selected.emit(profile)

    def _update_enabled(self) -> None:
        has_profile = self.profile_combo.count() > 0
        self.copy_button.setEnabled(has_profile)
        self.rename_button.setEnabled(has_profile)
        self.delete_button.setEnabled(has_profile and self.profile_combo.count() > 1)


__all__ = ["Poe2ProfileToolbar"]

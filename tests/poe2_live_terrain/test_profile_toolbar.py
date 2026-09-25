from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auto_modules.features.poe2.live_terrain import Poe2MonitorProfileStore
from auto_modules.ui.modes.poe2_live_terrain.profile_toolbar import Poe2ProfileToolbar


def test_profile_toolbar_lists_local_profiles(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    store = Poe2MonitorProfileStore(tmp_path)
    first = store.create("配置 1")
    store.create("配置 2")

    toolbar = Poe2ProfileToolbar(store)

    assert toolbar.profile_combo.count() == 2
    assert toolbar.current().profile_id == store.active().profile_id
    toolbar.deleteLater()

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QMenu


GAMEPAD_INPUTS = (
    ("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y"),
    ("LB", "LB"), ("RB", "RB"), ("LS", "L3"), ("RS", "R3"),
    ("UP", "十字键 上"), ("DOWN", "十字键 下"),
    ("LEFT", "十字键 左"), ("RIGHT", "十字键 右"),
    ("START", "START"), ("BACK", "BACK"),
    ("LS_UP", "移动 上（左摇杆）"), ("LS_DOWN", "移动 下（左摇杆）"),
    ("LS_LEFT", "移动 左（左摇杆）"), ("LS_RIGHT", "移动 右（左摇杆）"),
    ("LS_UP_LEFT", "移动 左上（左摇杆）"), ("LS_UP_RIGHT", "移动 右上（左摇杆）"),
    ("LS_DOWN_LEFT", "移动 左下（左摇杆）"), ("LS_DOWN_RIGHT", "移动 右下（左摇杆）"),
)
GAMEPAD_BUTTONS = tuple(value for value, _ in GAMEPAD_INPUTS)


class GamepadButtonPicker(QPushButton):
    """Compact checkable menu for selecting Xbox buttons and movement."""

    selectionChanged = Signal(object)

    def __init__(self, buttons=(), parent=None):
        super().__init__(parent)
        self._buttons = tuple()
        self._selection_order = []
        self._menu = QMenu(self)
        for value, label in GAMEPAD_INPUTS:
            action = self._menu.addAction(label)
            action.setData(value)
            action.setCheckable(True)
            action.toggled.connect(self._changed)
        self.setMenu(self._menu)
        self.setMinimumWidth(170)
        self.set_buttons(buttons)

    def buttons(self):
        return self._buttons

    def set_buttons(self, buttons):
        known = {value for value, _ in GAMEPAD_INPUTS}
        self._selection_order = list(dict.fromkeys(value for value in (buttons or ()) if value in known))
        wanted = set(self._selection_order)
        for action in self._menu.actions():
            action.blockSignals(True)
            action.setChecked(action.data() in wanted)
            action.blockSignals(False)
        self._sync()

    def _changed(self, _checked):
        checked = {action.data() for action in self._menu.actions() if action.isChecked()}
        self._selection_order = [value for value in self._selection_order if value in checked]
        self._selection_order.extend(
            action.data() for action in self._menu.actions()
            if action.isChecked() and action.data() not in self._selection_order
        )
        self._sync()
        self.selectionChanged.emit(self._buttons)

    def _sync(self):
        by_value = {action.data(): action for action in self._menu.actions()}
        selected = tuple(by_value[value] for value in self._selection_order if by_value[value].isChecked())
        self._buttons = tuple(action.data() for action in selected)
        self.setText(" + ".join(action.text() for action in selected) if selected else "选择手柄输入")

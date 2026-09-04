from __future__ import annotations

from dataclasses import dataclass
import inspect
from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING
import uuid

from PySide6.QtCore import QObject, QRunnable, QSignalBlocker, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .controller_widget import ControllerWidget
from .models import BindingProfile, CONTROLS, DualUiStatus, StateSnapshot, UiStatus
from .profile_store import load_profile, save_profile

if TYPE_CHECKING:
    from virtual_gamepad_client import VirtualGamepadClient


MOUSE_BINDINGS = (
    ("No mouse binding", ""),
    ("Mouse left button", "mouse:left"),
    ("Mouse right button", "mouse:right"),
    ("Mouse middle button", "mouse:middle"),
    ("Mouse side button X1", "mouse:x1"),
    ("Mouse side button X2", "mouse:x2"),
    ("Mouse horizontal movement", "mouse:move_x"),
    ("Mouse vertical movement", "mouse:move_y"),
)
MOUSE_BUTTON_SOURCES = {source for _, source in MOUSE_BINDINGS[1:6]}
MOUSE_MOVE_SOURCES = {"mouse:move_x", "mouse:move_y"}
KEYBOARD_KEYS = (
    *tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    *tuple("0123456789"),
    "Space",
    "Enter",
    "Escape",
    "Tab",
    "Backspace",
    "Shift",
    "Ctrl",
    "Alt",
    "Left",
    "Up",
    "Right",
    "Down",
    *tuple(f"F{number}" for number in range(1, 13)),
)
KEYBOARD_BINDINGS = (("No keyboard binding", ""),) + tuple(
    (key, f"keyboard:{key}") for key in KEYBOARD_KEYS
)

CONTROL_LABELS = {
    "A": "A · A 按钮",
    "B": "B · B 按钮",
    "X": "X · X 按钮",
    "Y": "Y · Y 按钮",
    "DPadUp": "方向键 · 上",
    "DPadDown": "方向键 · 下",
    "DPadLeft": "方向键 · 左",
    "DPadRight": "方向键 · 右",
    "Start": "菜单 · Start",
    "Back": "视图 · Back",
    "LeftStickClick": "左摇杆按下 · L3",
    "RightStickClick": "右摇杆按下 · R3",
    "LeftShoulder": "左肩键 · LB",
    "RightShoulder": "右肩键 · RB",
    "LeftStick": "左摇杆 · LS",
    "RightStick": "右摇杆 · RS",
    "LeftTrigger": "左扳机 · LT",
    "RightTrigger": "右扳机 · RT",
}


@dataclass(frozen=True)
class _ProfileSubmission:
    controller: int
    version: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class _PollResult:
    session_id: int
    status_payload: dict[str, Any] | None = None
    state_payload: dict[str, Any] | None = None
    applied_profiles: tuple[_ProfileSubmission, ...] = ()
    error: str = ""
    error_phase: str = ""

    @property
    def succeeded(self) -> bool:
        return not self.error


class _PollSignals(QObject):
    completed = Signal(object)
    command_completed = Signal(object)
    cleanup_completed = Signal(object)


@dataclass(frozen=True)
class _CommandResult:
    session_id: int
    action: str
    error: str = ""


@dataclass(frozen=True)
class _CleanupResult:
    succeeded: bool
    errors: tuple[str, ...] = ()


def _call_controller_method(
    client: Any,
    method_name: str,
    controller: int,
    *,
    source: str | None = None,
    sequence: int | None = None,
) -> None:
    method = getattr(client, method_name, None)
    if not callable(method):
        raise AttributeError(f"client does not expose {method_name}")
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        # The production client publishes the keyword-capable signature.  Do
        # not reinterpret an action-raised TypeError as a calling convention.
        method(controller, source=source, sequence=sequence)
        return

    parameters = tuple(signature.parameters.values())
    accepts_varargs = any(parameter.kind is inspect.Parameter.VAR_POSITIONAL for parameter in parameters)
    accepts_varkw = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters)
    accepts_positional = accepts_varargs or any(
        parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for parameter in parameters
    )
    names = {parameter.name for parameter in parameters}
    kwargs: dict[str, Any] = {}
    if not accepts_positional and (accepts_varkw or "controller" in names):
        kwargs["controller"] = controller
    if source is not None and (accepts_varkw or "source" in names):
        kwargs["source"] = source
    if sequence is not None and (accepts_varkw or "sequence" in names):
        kwargs["sequence"] = sequence
    method(*(controller,) if accepts_positional else (), **kwargs)


class _PollRunnable(QRunnable):
    """Perform host pipe work away from the Qt GUI event loop."""

    def __init__(
        self,
        *,
        client: Any,
        signals: _PollSignals,
        session_id: int,
        selected_controller: int,
        needs_connect: bool,
        profile_submissions: tuple[_ProfileSubmission, ...],
    ) -> None:
        super().__init__()
        self.client = client
        self.signals = signals
        self.session_id = session_id
        self.selected_controller = selected_controller
        self.needs_connect = needs_connect
        self.profile_submissions = profile_submissions

    def run(self) -> None:
        phase = "connection"
        try:
            if self.needs_connect:
                connect = getattr(self.client, "connect", None)
                if callable(connect):
                    # A failed Host must never hold the page's GUI thread hostage.
                    connect(timeout=0.25)
            if self.profile_submissions:
                phase = "profile_apply"
                for submission in self.profile_submissions:
                    self.client.request("set_config", submission.payload)
            phase = "status"
            status_payload = self.client.status()
            phase = "state"
            try:
                state_payload = self.client.state(self.selected_controller)
            except TypeError:
                state_payload = self.client.state()
            result = _PollResult(
                session_id=self.session_id,
                status_payload=status_payload,
                state_payload=state_payload,
                applied_profiles=self.profile_submissions,
            )
        except Exception as exc:
            # Client.close() invalidates a dead native-pipe handle so the next retry
            # opens a new connection instead of reusing an orphaned handle.
            close = getattr(self.client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            result = _PollResult(session_id=self.session_id, error=str(exc), error_phase=phase)
        try:
            self.signals.completed.emit(result)
        except RuntimeError:
            # The page may have been destroyed while this bounded worker was finishing.
            pass


class _CommandRunnable(QRunnable):
    """Dispatch a control-button request without blocking the GUI thread."""

    def __init__(
        self,
        *,
        client: Any,
        signals: _PollSignals,
        session_id: int,
        action: str,
        controller: int,
        lifecycle_source: str,
        lifecycle_sequence: int,
    ) -> None:
        super().__init__()
        self.client = client
        self.signals = signals
        self.session_id = session_id
        self.action = action
        self.controller = controller
        self.lifecycle_source = lifecycle_source
        self.lifecycle_sequence = lifecycle_sequence

    def run(self) -> None:
        try:
            _call_controller_method(
                self.client,
                self.action,
                self.controller,
                source=self.lifecycle_source,
                sequence=self.lifecycle_sequence,
            )
            result = _CommandResult(session_id=self.session_id, action=self.action)
        except Exception as exc:
            close = getattr(self.client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            result = _CommandResult(session_id=self.session_id, action=self.action, error=str(exc))
        try:
            self.signals.command_completed.emit(result)
        except RuntimeError:
            pass


class _CleanupRunnable(QRunnable):
    """Use an independent client so page shutdown never waits on a poll request lock."""

    MAX_ATTEMPTS = 2

    def __init__(
        self,
        *,
        client: Any,
        signals: _PollSignals,
        lifecycle_source: str,
        operations: tuple[tuple[int, str, int], ...],
    ) -> None:
        super().__init__()
        self.client = client
        self.signals = signals
        self.lifecycle_source = lifecycle_source
        self.operations = operations

    def run(self) -> None:
        errors: list[str] = []
        connect = getattr(self.client, "connect", None)
        if callable(connect):
            try:
                connect(timeout=0.25)
            except Exception as exc:
                errors.append(str(exc))
        for controller, action, sequence in self.operations:
            operation_error = ""
            for _attempt in range(self.MAX_ATTEMPTS):
                try:
                    _call_controller_method(
                        self.client,
                        action,
                        controller,
                        source=self.lifecycle_source,
                        sequence=sequence,
                    )
                    operation_error = ""
                    break
                except Exception as exc:
                    operation_error = str(exc)
            if operation_error:
                errors.append(f"Controller {controller} {action} failed: {operation_error}")
        close = getattr(self.client, "close", None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                errors.append(str(exc))
        try:
            self.signals.cleanup_completed.emit(_CleanupResult(not errors, tuple(errors)))
        except RuntimeError:
            pass


class GamepadPage(QWidget):
    """Embeddable configuration and live-status page for two virtual controllers."""

    shutdown_finished = Signal(bool, str)

    POLL_SUCCESS_INTERVAL_MS = 250
    POLL_FAILURE_INITIAL_MS = 500
    POLL_FAILURE_MAX_MS = 5_000
    SHUTDOWN_TIMEOUT_MS = 2_000

    def __init__(
        self,
        client: VirtualGamepadClient,
        *,
        profile_root: Path,
        parent: QWidget | None = None,
        demo: bool = False,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.client = client
        self._client_factory = client_factory or self._make_client_factory(client)
        self.demo = demo
        self.profile_paths = self._profile_paths(Path(profile_root))
        self._profile_load_error = ""
        self._profile_apply_error = ""
        self._host_error = ""
        self._action_message = ""
        self.profiles = self._load_profiles_safely()
        self.selected_controller = 1
        self.profile = self.profiles[1]
        self._connected = demo
        self._profiles_applied = False
        self._pending_profile_controllers = set() if demo else {1, 2}
        self._profile_versions = {1: 0, 2: 0}
        self._last_status = UiStatus()
        self._dual_status = DualUiStatus()
        self._poll_in_flight = False
        self._command_in_flight = False
        self._shutting_down = False
        self._shutdown_failed = False
        self._shutdown_result_sent = False
        self._poll_session_id = 0
        self._lifecycle_source = f"virtual-gamepad-page:{uuid.uuid4().hex}"
        self._lifecycle_sequence = 0
        self._failure_delay_ms = self.POLL_FAILURE_INITIAL_MS

        self.setObjectName("gamepadPage")
        self.setStyleSheet(
            """
            QWidget#gamepadPage { background: #0B1220; color: #E5EEF7; }
            QWidget#gamepadPage QLabel[role="muted"] { color: #91A4B8; }
            QWidget#gamepadPage QFrame#controllerSurface,
            QWidget#gamepadPage QFrame#bindingCard {
                background: #0F1A28; border: 1px solid #26364A; border-radius: 12px;
            }
            QWidget#gamepadPage QLabel[role="section-title"] {
                color: #E5EEF7; font-size: 15px; font-weight: 700;
            }
            QWidget#gamepadPage QLabel#selectedControlValue {
                color: #38BDF8; font-size: 14px; font-weight: 700;
                background: #10273A; border: 1px solid #24516D; border-radius: 6px; padding: 5px 8px;
            }
            QWidget#gamepadPage QComboBox,
            QWidget#gamepadPage QDoubleSpinBox {
                min-height: 32px; background: #101C2B; border: 1px solid #33465C;
                border-radius: 6px; padding: 0 8px;
            }
            QWidget#gamepadPage QComboBox::drop-down { border: 0; width: 28px; }
            QWidget#gamepadPage QComboBox QAbstractItemView {
                background: #111C2B; border: 1px solid #33465C; selection-background-color: #0E7490;
            }
            QWidget#gamepadPage QLineEdit {
                min-height: 30px; background: #0F1A28; border: 1px solid #33465C;
                border-radius: 6px; padding: 0 8px;
            }
            QWidget#gamepadPage QFrame#cardDivider {
                background: #26364A; border: 0; max-height: 1px;
            }
            QWidget#gamepadPage QFormLayout QLabel { color: #B8C7D9; }
            QWidget#gamepadPage QPushButton[role="success"] {
                color: #06140B; background: #22C55E; border-color: #86EFAC;
            }
            QWidget#gamepadPage QPushButton[role="warning"] {
                color: #1C1200; background: #F59E0B; border-color: #FCD34D;
            }
            QWidget#gamepadPage QPushButton[role="danger"] {
                color: #FFF1F2; background: #7F1D1D; border-color: #EF4444;
            }
            """
        )
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh)
        self._poll_signals = _PollSignals(self)
        self._poll_signals.completed.connect(self._on_poll_completed)
        self._poll_signals.command_completed.connect(self._on_command_completed)
        self._poll_signals.cleanup_completed.connect(self._on_cleanup_completed)
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setSingleShot(True)
        self._shutdown_timer.timeout.connect(self._on_shutdown_timeout)
        self._update_lifecycle_controls()
        self._update_message_label()

    @staticmethod
    def _profile_paths(profile_root: Path) -> dict[int, Path]:
        """Accept a profile directory, while retaining the legacy file-path entry point."""
        if profile_root.suffix:
            return {
                1: profile_root,
                2: profile_root.with_name("controller-2.json"),
            }
        return {
            1: profile_root / "controller-1.json",
            2: profile_root / "controller-2.json",
        }

    @staticmethod
    def _make_client_factory(client: Any) -> Callable[[], Any]:
        client_type = type(client)
        pipe_path = getattr(client, "pipe_path", None)

        def create() -> Any:
            if pipe_path is not None:
                try:
                    return client_type(pipe_path=pipe_path)
                except TypeError:
                    pass
            return client_type()

        return create

    def _load_profiles_safely(self) -> dict[int, BindingProfile]:
        profiles: dict[int, BindingProfile] = {}
        errors: list[str] = []
        for controller, path in self.profile_paths.items():
            try:
                profiles[controller] = load_profile(path)
            except Exception as exc:
                profiles[controller] = BindingProfile()
                errors.append(f"Controller {controller} profile could not be loaded: {exc}")
        self._profile_load_error = " | ".join(errors)
        return profiles

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.driver_label = QLabel("Driver: checking")
        self.device_label = QLabel("Device: checking")
        self.state_label = QLabel("State: Disconnected")
        self.controller_one_status = QLabel("C1: paused")
        self.controller_two_status = QLabel("C2: paused")
        for label in (
            self.driver_label,
            self.device_label,
            self.state_label,
            self.controller_one_status,
            self.controller_two_status,
        ):
            label.setProperty("role", "status-value")
            top.addWidget(label)
        self.message_label = QLabel("")
        self.message_label.setProperty("role", "muted")
        top.addWidget(self.message_label, 1)
        self.start_button = QPushButton("Start / Resume")
        self.start_button.setProperty("role", "success")
        self.pause_button = QPushButton("Pause")
        self.pause_button.setProperty("role", "warning")
        self.reset_button = QPushButton("Emergency Reset")
        self.reset_button.setProperty("role", "danger")
        self.start_button.clicked.connect(self._start)
        self.pause_button.clicked.connect(self._pause)
        self.reset_button.clicked.connect(self._reset)
        top.addWidget(self.start_button)
        top.addWidget(self.pause_button)
        top.addWidget(self.reset_button)
        layout.addLayout(top)

        selector_row = QHBoxLayout()
        self.controller_one_selector = QPushButton("Controller 1 · F7")
        self.controller_two_selector = QPushButton("Controller 2 · F8")
        for selector in (self.controller_one_selector, self.controller_two_selector):
            selector.setProperty("role", "mode")
            selector.setCheckable(True)
        self.controller_one_selector.clicked.connect(lambda: self._select_controller(1))
        self.controller_two_selector.clicked.connect(lambda: self._select_controller(2))
        selector_row.addWidget(self.controller_one_selector)
        selector_row.addWidget(self.controller_two_selector)
        shortcuts = QLabel("F9: emergency reset and unlock both controllers")
        shortcuts.setProperty("role", "muted")
        selector_row.addWidget(shortcuts, 1)
        layout.addLayout(selector_row)

        content = QHBoxLayout()
        content.setSpacing(14)
        content.setContentsMargins(0, 4, 0, 0)

        controller_surface = QFrame()
        controller_surface.setObjectName("controllerSurface")
        controller_surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        controller_layout = QVBoxLayout(controller_surface)
        controller_layout.setContentsMargins(8, 8, 8, 8)
        self.controller = ControllerWidget()
        self.controller.control_clicked.connect(self._select_control)
        controller_layout.addWidget(self.controller)
        content.addWidget(controller_surface, 1)

        side = QFrame()
        side.setObjectName("bindingCard")
        side.setMinimumWidth(350)
        side.setMaximumWidth(430)
        side.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(16, 16, 16, 14)
        side_layout.setSpacing(10)
        title = QLabel("按键映射")
        title.setProperty("role", "section-title")
        side_layout.addWidget(title)
        editor_hint = QLabel("在左侧手柄上点选，或从下拉菜单选择要配置的虚拟控件。")
        editor_hint.setProperty("role", "muted")
        editor_hint.setWordWrap(True)
        side_layout.addWidget(editor_hint)
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(9)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.control_combo = QComboBox()
        for control in CONTROLS:
            self.control_combo.addItem(CONTROL_LABELS.get(control, control), control)
        self.control_combo.currentIndexChanged.connect(self._control_combo_changed)
        self.selected_label = QLabel("Select a control")
        self.selected_label.setObjectName("selectedControlValue")
        self.binding_edit = QLineEdit()
        self.binding_edit.setReadOnly(True)
        self.binding_edit.setPlaceholderText("未绑定键盘")
        form.addRow("虚拟控件", self.control_combo)
        form.addRow("当前选择", self.selected_label)
        form.addRow("键盘绑定", self.binding_edit)
        keyboard_row = QHBoxLayout()
        self.keyboard_combo = QComboBox()
        for label, source in KEYBOARD_BINDINGS:
            self.keyboard_combo.addItem(label, source)
        self.set_keyboard_button = QPushButton("替换")
        self.add_keyboard_button = QPushButton("追加")
        self.set_keyboard_button.clicked.connect(self._set_keyboard_binding)
        self.add_keyboard_button.clicked.connect(self._add_keyboard_binding)
        keyboard_row.addWidget(self.keyboard_combo, 1)
        keyboard_row.addWidget(self.set_keyboard_button)
        keyboard_row.addWidget(self.add_keyboard_button)
        form.addRow("选择键盘", keyboard_row)
        self.mouse_combo = QComboBox()
        for label, source in MOUSE_BINDINGS:
            self.mouse_combo.addItem(label, source)
        # Mouse bindings stay dropdown-only: this page never captures mouse input.
        self.mouse_combo.currentIndexChanged.connect(self._mouse_binding_changed)
        form.addRow("鼠标绑定", self.mouse_combo)
        self.mouse_sensitivity_spin = QDoubleSpinBox()
        self.mouse_sensitivity_spin.setRange(0.25, 20.0)
        self.mouse_sensitivity_spin.setSingleStep(0.25)
        self.mouse_sensitivity_spin.setDecimals(2)
        self.mouse_sensitivity_spin.setSuffix(" x")
        self.mouse_sensitivity_spin.setValue(self.profile.mouse_sensitivity)
        self.mouse_sensitivity_spin.valueChanged.connect(self._mouse_sensitivity_changed)
        form.addRow("RS 鼠标灵敏度", self.mouse_sensitivity_spin)
        self.mouse_passthrough_check = QCheckBox("镜像到 RS 时保留原生鼠标移动")
        self.mouse_passthrough_check.setChecked(self.profile.mouse_move_passthrough)
        self.mouse_passthrough_check.toggled.connect(self._mouse_passthrough_changed)
        form.addRow("鼠标移动", self.mouse_passthrough_check)
        side_layout.addLayout(form)
        card_divider = QFrame()
        card_divider.setObjectName("cardDivider")
        card_divider.setFrameShape(QFrame.Shape.HLine)
        side_layout.addWidget(card_divider)
        action_row = QHBoxLayout()
        self.clear_keyboard_button = QPushButton("清空键盘")
        self.clear_button = QPushButton("清空当前控件")
        self.clear_keyboard_button.clicked.connect(self._clear_keyboard_binding)
        self.clear_button.clicked.connect(self._clear_binding)
        action_row.addWidget(self.clear_keyboard_button)
        action_row.addWidget(self.clear_button)
        side_layout.addLayout(action_row)
        profile_row = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("当前控制器配置")
        self.save_button = QPushButton("保存配置")
        self.save_button.clicked.connect(self._save_profile)
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(self.save_button)
        side_layout.addLayout(profile_row)
        shortcut_label = QLabel(
            "Controller 1 start/pause: F7 · Controller 2 start/pause: F8 · Emergency reset: F9"
        )
        shortcut_label.setObjectName("shortcutLabel")
        shortcut_label.setProperty("role", "muted")
        shortcut_label.setWordWrap(True)
        side_layout.addWidget(shortcut_label)
        content.addWidget(side)
        layout.addLayout(content, 1)
        self.controller_one_selector.setChecked(True)
        self._select_control(CONTROLS[0])

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_poll(0)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        if not self._shutting_down:
            self._replace_page_client_after_cancellation()
        super().hideEvent(event)

    def _replace_page_client_after_cancellation(self) -> None:
        """Cancel stale page I/O before a future show starts a separate session."""
        self._poll_session_id += 1
        self._poll_in_flight = False
        self._command_in_flight = False
        self._connected = self.demo
        old_client = self.client
        close = getattr(old_client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        try:
            self.client = self._client_factory()
        except Exception as exc:
            self._host_error = f"Could not create a gamepad client: {exc}"
            self.client = old_client
        self._update_message_label()

    def _schedule_poll(self, delay_ms: int) -> None:
        if self._shutting_down or not self.isVisible() or self._poll_in_flight:
            return
        self._timer.start(max(0, delay_ms))

    def refresh(self) -> None:
        """Queue one status pass; all host I/O remains in the worker thread."""
        if self._shutting_down or not self.isVisible() or self._poll_in_flight:
            return
        self._timer.stop()
        submissions = tuple(
            _ProfileSubmission(
                controller=controller,
                version=self._profile_versions[controller],
                payload={**self.profiles[controller].to_payload(), "controller": controller},
            )
            for controller in sorted(self._pending_profile_controllers)
        )
        self._poll_in_flight = True
        QThreadPool.globalInstance().start(
            _PollRunnable(
                client=self.client,
                signals=self._poll_signals,
                session_id=self._poll_session_id,
                selected_controller=self.selected_controller,
                needs_connect=not self._connected and not self.demo,
                profile_submissions=submissions,
            )
        )

    def _on_poll_completed(self, result: _PollResult) -> None:
        if result.session_id != self._poll_session_id:
            return
        self._poll_in_flight = False
        if self._shutting_down:
            return
        if not result.succeeded:
            self._connected = self.demo
            self._last_status = UiStatus(message=result.error)
            self._dual_status = DualUiStatus()
            if result.error_phase == "profile_apply":
                # Retry complete configuration only on the bounded failure cadence.
                self._pending_profile_controllers.update({1, 2})
                self._profile_apply_error = f"Could not apply saved profiles: {result.error}"
            else:
                self._host_error = result.error
            self._render_status(StateSnapshot())
            self._schedule_poll(self._failure_delay_ms)
            self._failure_delay_ms = min(self._failure_delay_ms * 2, self.POLL_FAILURE_MAX_MS)
            return

        self._connected = True
        self._failure_delay_ms = self.POLL_FAILURE_INITIAL_MS
        self._host_error = ""
        self._last_status = UiStatus.from_payload(result.status_payload or {})
        self._dual_status = DualUiStatus.from_payload(result.status_payload or {})
        if result.applied_profiles:
            current_applied = {
                submission.controller
                for submission in result.applied_profiles
                if self._profile_versions[submission.controller] == submission.version
            }
            self._pending_profile_controllers.difference_update(current_applied)
            if not self._pending_profile_controllers:
                self._profiles_applied = True
            if current_applied == {1, 2}:
                self._profile_apply_error = ""
        self._render_status(StateSnapshot.from_payload(result.state_payload or {}))
        self._schedule_poll(0 if self._pending_profile_controllers else self.POLL_SUCCESS_INTERVAL_MS)

    def _render_status(self, state: StateSnapshot) -> None:
        self.driver_label.setText(f"Driver: {'ready' if self._last_status.driver_installed else 'missing'}")
        self.device_label.setText(f"Device: {'connected' if self._last_status.device_connected else 'unavailable'}")
        self.state_label.setText(f"State: {self._last_status.run_state}")
        self.controller_one_status.setText(f"C1: {self._dual_status.for_controller(1).run_state}")
        self.controller_two_status.setText(f"C2: {self._dual_status.for_controller(2).run_state}")
        self.controller.set_snapshot(state)
        self.controller.set_profile(self.profile)
        self._update_lifecycle_controls()
        self._update_message_label()

    def _lifecycle_ready(self) -> bool:
        if self._shutting_down or self._shutdown_failed:
            return False
        return self.demo or (
            self._connected
            and self._profiles_applied
            and not self._pending_profile_controllers
        )

    def _update_lifecycle_controls(self) -> None:
        enabled = self._lifecycle_ready() and not self._command_in_flight
        for button in (self.start_button, self.pause_button, self.reset_button):
            button.setEnabled(enabled)

    def _next_lifecycle_sequence(self) -> int:
        self._lifecycle_sequence += 1
        return self._lifecycle_sequence

    def _dispatch_command(self, action: str) -> None:
        if self._shutting_down or self._command_in_flight:
            return
        if not self._lifecycle_ready():
            self._show_message("Virtual gamepad is preparing profiles; lifecycle controls will be enabled when ready.")
            return
        self._command_in_flight = True
        self._update_lifecycle_controls()
        QThreadPool.globalInstance().start(
            _CommandRunnable(
                client=self.client,
                signals=self._poll_signals,
                session_id=self._poll_session_id,
                action=action,
                controller=self.selected_controller,
                lifecycle_source=self._lifecycle_source,
                lifecycle_sequence=self._next_lifecycle_sequence(),
            )
        )

    def _on_command_completed(self, result: _CommandResult) -> None:
        if result.session_id != self._poll_session_id:
            return
        self._command_in_flight = False
        self._update_lifecycle_controls()
        if self._shutting_down:
            return
        if result.error:
            self._invalidate_client(result.error)

    def _on_cleanup_completed(self, result: _CleanupResult) -> None:
        if not result.succeeded:
            self._finish_shutdown(False, "; ".join(result.errors))
            return
        self._finish_shutdown(True, "")

    def _on_shutdown_timeout(self) -> None:
        self._finish_shutdown(False, "Timed out while waiting for virtual gamepad reset/pause cleanup.")

    def _finish_shutdown(self, succeeded: bool, message: str) -> None:
        if self._shutdown_result_sent:
            return
        self._shutdown_result_sent = True
        self._shutdown_timer.stop()
        self._shutdown_failed = not succeeded
        if not succeeded:
            # Keep the page open in its safe, disabled state.  A later close
            # request starts a fresh, independently fenced cleanup attempt.
            self._shutting_down = False
            self._host_error = message
        self._update_lifecycle_controls()
        self._update_message_label()
        self.shutdown_finished.emit(succeeded, message)

    def _select_controller(self, controller: int) -> None:
        if controller not in self.profiles:
            return
        self.selected_controller = controller
        self.profile = self.profiles[controller]
        self.controller_one_selector.setChecked(controller == 1)
        self.controller_two_selector.setChecked(controller == 2)
        self._show_control(self._selected_control())
        self.controller.set_profile(self.profile)
        self.refresh()

    def _apply_all_profiles(self) -> None:
        if self.demo:
            return
        self._pending_profile_controllers.update({1, 2})
        self._profiles_applied = False
        self._update_lifecycle_controls()
        self._schedule_poll(0)

    def _control_combo_changed(self, index: int) -> None:
        control = str(self.control_combo.itemData(index) or "")
        if control:
            self.controller.set_selected_control(control)
        self._show_control(control)

    @staticmethod
    def _find_combo_data(combo: QComboBox, source: str) -> int:
        """Find persisted sources even if an older profile used different casing."""
        wanted = source.casefold()
        for index in range(combo.count()):
            if str(combo.itemData(index) or "").casefold() == wanted:
                return index
        return -1

    def _select_control(self, control: str) -> None:
        """Select a diagram/dropdown control and always refresh every editor field."""
        if control not in CONTROLS:
            return
        index = self._find_combo_data(self.control_combo, control)
        if index < 0:
            return
        with QSignalBlocker(self.control_combo):
            self.control_combo.setCurrentIndex(index)
        self.controller.set_selected_control(control)
        # setCurrentIndex does not emit for an already selected item.  Rendering
        # explicitly here prevents bindings from the previously selected control
        # being left visible in the editor.
        self._show_control(control)

    def _show_control(self, control: str) -> None:
        self.selected_label.setText(control or "Select a control")
        sources = self.profile.bindings.get(control, []) if control else []
        keyboard_sources = [source for source in sources if not source.lower().startswith("mouse:")]
        self.binding_edit.setText(", ".join(keyboard_sources))
        with QSignalBlocker(self.keyboard_combo):
            keyboard_source = keyboard_sources[0] if keyboard_sources else ""
            index = self._find_combo_data(self.keyboard_combo, keyboard_source)
            self.keyboard_combo.setCurrentIndex(index if index >= 0 else 0)
        mouse_source = next((source for source in sources if source.lower().startswith("mouse:")), "")
        with QSignalBlocker(self.mouse_combo):
            index = self._find_combo_data(self.mouse_combo, mouse_source)
            self.mouse_combo.setCurrentIndex(index if index >= 0 else 0)
        with QSignalBlocker(self.mouse_sensitivity_spin):
            self.mouse_sensitivity_spin.setValue(self.profile.mouse_sensitivity)
        with QSignalBlocker(self.mouse_passthrough_check):
            self.mouse_passthrough_check.setChecked(self.profile.mouse_move_passthrough)

    def _selected_control(self) -> str:
        return str(self.control_combo.currentData() or "")

    def _selected_keyboard_source(self) -> str:
        return str(self.keyboard_combo.currentData() or "")

    def _set_keyboard_binding(self) -> None:
        control = self._selected_control()
        source = self._selected_keyboard_source()
        if not control or not source:
            return
        existing = self.profile.bindings.get(control, [])
        mouse_sources = [item for item in existing if item.lower().startswith("mouse:")]
        self.profile.bindings[control] = [source, *mouse_sources]
        self._show_control(control)
        self.controller.set_profile(self.profile)
        self._apply_profile()

    def _add_keyboard_binding(self) -> None:
        control = self._selected_control()
        source = self._selected_keyboard_source()
        if not control or not source:
            return
        existing = list(self.profile.bindings.get(control, []))
        if not any(item.lower() == source.lower() for item in existing):
            mouse_sources = [item for item in existing if item.lower().startswith("mouse:")]
            keyboard_sources = [item for item in existing if not item.lower().startswith("mouse:")]
            self.profile.bindings[control] = [*keyboard_sources, source, *mouse_sources]
        self._show_control(control)
        self.controller.set_profile(self.profile)
        self._apply_profile()

    def _clear_keyboard_binding(self) -> None:
        control = self._selected_control()
        if control:
            existing = self.profile.bindings.get(control, [])
            mouse_sources = [item for item in existing if item.lower().startswith("mouse:")]
            if mouse_sources:
                self.profile.bindings[control] = mouse_sources
            else:
                self.profile.bindings.pop(control, None)
            self._show_control(control)
            self.controller.set_profile(self.profile)
            self._apply_profile()

    def _mouse_binding_changed(self, _index: int) -> None:
        control = self._selected_control()
        if not control:
            return
        source = self.mouse_combo.currentData()
        existing = list(self.profile.bindings.get(control, []))
        if not source:
            updated = [item for item in existing if not item.lower().startswith("mouse:")]
        elif source in MOUSE_BUTTON_SOURCES:
            updated = [item for item in existing if item.lower() not in MOUSE_BUTTON_SOURCES]
            updated.append(source)
        elif source in MOUSE_MOVE_SOURCES:
            updated = [item for item in existing if item.lower() != source]
            updated.append(source)
        else:
            updated = existing
        if updated:
            self.profile.bindings[control] = updated
        else:
            self.profile.bindings.pop(control, None)
        keyboard_sources = [item for item in updated if not item.lower().startswith("mouse:")]
        self.binding_edit.setText(", ".join(keyboard_sources))
        self.controller.set_profile(self.profile)
        self._apply_profile()

    def _mouse_sensitivity_changed(self, value: float) -> None:
        self.profile.mouse_sensitivity = float(value)
        self._apply_profile()

    def _mouse_passthrough_changed(self, checked: bool) -> None:
        self.profile.mouse_move_passthrough = checked
        self._apply_profile()

    def _clear_binding(self) -> None:
        control = self._selected_control()
        self.profile.bindings.pop(control, None)
        self._show_control(control)
        self.controller.set_profile(self.profile)
        self._apply_profile()

    def _apply_profile(self) -> bool:
        if self.demo:
            try:
                payload = self.profile.to_payload()
                if self.selected_controller != 1:
                    payload["controller"] = self.selected_controller
                self.client.request("set_config", payload)
                return True
            except Exception as exc:
                self._show_message(f"Could not apply bindings: {exc}")
                return False
        self._profile_versions[self.selected_controller] += 1
        self._pending_profile_controllers.add(self.selected_controller)
        self._profiles_applied = False
        self._update_lifecycle_controls()
        self._schedule_poll(0)
        return True

    def _save_profile(self) -> None:
        try:
            save_profile(self.profile_paths[self.selected_controller], self.profile)
            if self._apply_profile():
                self._show_message(f"Saved locally; applying Controller {self.selected_controller}")
            else:
                self._show_message("Saved locally; host was not updated")
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _start(self) -> None:
        self._dispatch_command("start")

    def _pause(self) -> None:
        self._dispatch_command("pause")

    def _reset(self) -> None:
        self._dispatch_command("reset")

    def _show_message(self, message: str) -> None:
        self._action_message = message
        self._update_message_label()

    def show_host_error(self, message: str) -> None:
        """Surface workbench Host-start failures without exposing page internals."""
        self._host_error = message
        self._update_message_label()

    def _update_message_label(self) -> None:
        messages = (
            self._profile_load_error,
            self._profile_apply_error,
            self._host_error,
            self._action_message,
            self._last_status.message,
        )
        self.message_label.setText(next((message for message in messages if message), ""))

    def _invalidate_client(self, message: str) -> None:
        self._connected = self.demo
        self._host_error = message
        close = getattr(self.client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        self._update_message_label()
        self._schedule_poll(self._failure_delay_ms)

    def shutdown(self) -> None:
        """Cancel page I/O first, then independently reset and pause both controllers."""
        if self._shutting_down:
            return
        # A failed close attempt is deliberately recoverable: do not let a
        # transient pipe error turn the standalone window into an unclosable
        # process.  Lifecycle controls remain disabled until cleanup succeeds.
        self._shutdown_result_sent = False
        self._shutdown_failed = False
        self._shutting_down = True
        self._timer.stop()
        self._update_lifecycle_controls()
        self._poll_session_id += 1
        self._poll_in_flight = False
        self._command_in_flight = False
        page_client = self.client
        close = getattr(page_client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        try:
            cleanup_client = self._client_factory()
        except Exception as exc:
            self._host_error = f"Could not create cleanup client: {exc}"
            self._update_message_label()
            self._finish_shutdown(False, self._host_error)
            return
        operations = tuple(
            (controller, action, self._next_lifecycle_sequence())
            for controller in (1, 2)
            for action in ("reset", "pause")
        )
        self._shutdown_timer.start(self.SHUTDOWN_TIMEOUT_MS)
        QThreadPool.globalInstance().start(
            _CleanupRunnable(
                client=cleanup_client,
                signals=self._poll_signals,
                lifecycle_source=self._lifecycle_source,
                operations=operations,
            )
        )

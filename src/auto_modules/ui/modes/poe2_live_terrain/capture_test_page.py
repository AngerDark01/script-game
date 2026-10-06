"""PoE2 capture-only test page used to inspect live evidence and terrain data."""

from __future__ import annotations

import math
import time
import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from auto_modules.adapters.windows import find_process_window, is_process_foreground
from auto_modules.core.localization.local_matcher import LocalMapMatcher
from auto_modules.core.localization.map_runtime import MapRuntime
from auto_modules.core.localization.displacement import inverse_transform_local_displacement
from auto_modules.core.routing.geometry import point_distance
from auto_modules.features.poe2.live_terrain import get_terrain_logger
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.absolute_registrar import (
    reference_boundary_layer,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.models import (
    HybridFrame,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow import (
    ClosedLoopMotionController,
    ControlMode,
    FollowState,
    MapIdentity,
    PositionSample,
    ProgramFollowOutput,
    RoleId,
    SimulatedFollowRuntime,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.command_role_tracker import (
    CommandRoleTracker,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization import (
    DualFirstFrameExperiment,
    DualVisualTracker,
    MarkerColorProfile,
    Poe2DualMemoryAnchorProvider,
    Poe2DualPlayerPositionSource,
    build_poe2_dual_first_frame_registrar,
    detect_saturated_marker_observation,
    inspect_minimap_contact,
    marker_candidates_from_observation,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.occlusion_archive import (
    save_dual_occlusion_evidence,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.dual_motion import (
    RolePredictionHint,
)
from auto_modules.features.poe2.live_terrain.experimental.recovery.controller import (
    RecoveryController,
    RecoveryObservation,
)
from auto_modules.features.poe2.live_terrain.player_position import find_process_id
from auto_modules.features.poe2.live_terrain.orientation import TerrainOrientation
from auto_modules.features.poe2.live_terrain.movement import (
    native_route_vector_for_program_output,
)
from auto_modules.features.poe2.live_terrain.terrain_reference import build_reference
from auto_modules.ui.widgets import ScalableMapWidget
from auto_modules.ui.widgets.aspect_preview import AspectPreviewLabel

from .capture_monitor_window import Poe2CaptureMonitorWindow
from .localization_control_dialog import Poe2LocalizationControlDialog
from .dual_motion_worker import Poe2DualFirstFrameWorker, Poe2DualMotionWorker
from .presenter import (
    build_localization_presentation,
    frame_pixmap,
    localization_display_point,
    localization_source_point,
    prepare_localization_map,
    present_localization_overlay,
    present_player_position_overlay,
    present_snapshot,
    terrain_pixmap,
)

if TYPE_CHECKING:
    from auto_modules.features.poe2.live_terrain.player_position import (
        PlayerPositionSample,
    )


class _UiLogHandler(logging.Handler, QObject):
    """Forward the PoE2 feature logger to the page's bounded log sidebar."""

    message_emitted = Signal(str)

    def __init__(self, parent: QObject) -> None:
        QObject.__init__(self, parent)
        logging.Handler.__init__(self)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.message_emitted.emit(self.format(record))
        except Exception:
            self.handleError(record)


class Poe2CaptureTestPage(QWidget):
    """Capture screenshots and native terrain without starting localization."""

    _FOLLOW_START_MAX_FRAME_AGE_MS = 300
    _FOLLOW_RUNTIME_MAX_FRAME_AGE_MS = 700
    # Short capture stalls should not immediately pay for a global re-anchor.
    _FOLLOW_STALE_RECOVERY_AFTER_MS = 8_000
    _FOLLOW_FOREGROUND_CACHE_MS = 250
    _DUAL_RECOVERY_COOLDOWN_MS = 10_000
    _DUAL_WORKER_DRAIN_INTERVAL_MS = 33
    _PROGRAM_DIAGNOSTICS_INTERVAL_MS = 5_000
    _FOLLOW_REJECTED_VISUAL_REANCHOR_COUNT = 3
    # A fresh marker can disagree with command odometry while still being a
    # continuous local step.  This bound is deliberately separate from the
    # estimator's innovation gate: it limits only the fallback visual rebase.
    _FOLLOW_VISUAL_CONTINUITY_MAX_SPEED = 180.0
    _FOLLOW_VISUAL_CONTINUITY_MAX_STEP = 32.0
    # This is the maximum interval between two visual anchors for the
    # continuity fallback.  It is intentionally larger than
    # ``_FOLLOW_RUNTIME_MAX_FRAME_AGE_MS``: the latter describes freshness of
    # the current frame, while this value describes a capture gap between
    # consecutive frames.  A queued/low-rate frame can be fresh now even when
    # the previous delivered frame is more than 700 ms old.
    _FOLLOW_VISUAL_CONTINUITY_MAX_GAP_MS = 3_000
    _FOLLOW_COLD_START_LOG_INTERVAL_MS = 1_000
    _FOLLOW_FOREGROUND_WAIT_MS = 10_000
    _FOLLOW_FOREGROUND_LOG_INTERVAL_MS = 1_000
    # Give the user time to move focus back to PoE2 after pressing the
    # workbench button.  This gate is intentionally above ProgramFollowOutput
    # so no Host lease or controller report can be created during the delay.
    _FOLLOW_COMMAND_ARM_DELAY_MS = 6_000
    _FOLLOW_COMMAND_ARM_LOG_INTERVAL_MS = 1_000

    def __init__(
        self,
        service: Any,
        *,
        archive: Any,
        sample_archive: Any | None = None,
        stitching_session_factory: Callable[[], Any] | None = None,
        stitching_archive: Any | None = None,
        monitor_config: Any,
        preview_provider: Callable[[Any], Any] | None,
        recognizer: Any | None = None,
        player_position_source: Any | None = None,
        dual_player_position_source: Any | None = None,
        dual_first_frame_factory: Callable[[Any], Any] | None = None,
        dual_motion_tracker_factory: Callable[[Any], Any] | None = None,
        program_output_factory: Callable[[int], Any] | None = None,
        hybrid_localization_factory: Callable[[Any, Callable[[], Any]], Any] | None = None,
        multiframe_localization_factory: Callable[[Any, Callable[[], Any]], Any] | None = None,
        open_config: Callable[[], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.archive = archive
        self.sample_archive = sample_archive
        self.stitching_session_factory = stitching_session_factory
        self.stitching_archive = stitching_archive
        self.monitor_config = monitor_config
        self.preview_provider = preview_provider
        self.recognizer = recognizer
        self.player_position_source = player_position_source
        self.dual_player_position_source = dual_player_position_source
        self.dual_first_frame_factory = dual_first_frame_factory
        self.dual_motion_tracker_factory = dual_motion_tracker_factory
        self.program_output_factory = program_output_factory
        self.hybrid_localization_factory = hybrid_localization_factory
        self.multiframe_localization_factory = multiframe_localization_factory
        self.open_config_callback = open_config
        self.capture_monitor_window = None
        self._logger = get_terrain_logger()
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(self._preview_interval())
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.hybrid_timer = QTimer(self)
        self.hybrid_timer.setInterval(self._localization_interval())
        self.hybrid_timer.timeout.connect(self._tick_hybrid_localization)
        self._snapshot = None
        self._player_position: PlayerPositionSample | None = None
        self._terrain_base_pixmap = None
        self.map_follow_zoom_multiplier = 2.4
        self._hybrid_experiment = None
        self._last_hybrid_state = None
        self._last_dual_first_frame_result = None
        self._dual_first_frame_read_count = 0
        self._dual_preview_active = False
        self._dual_initial_frame = None
        self._dual_initial_candidates = ()
        self._dual_motion_tracker = None
        self._dual_map_source_size = None
        self._dual_motion_frame_count = 0
        self._dual_last_recovery_at_ms = None
        self._dual_map_transform = None
        self._dual_follow_reference = None
        self._latest_dual_state = None
        self._latest_dual_raw = None
        self._latest_dual_combined = None
        self._latest_dual_processed = None
        self._latest_dual_captured_at_ms: int | None = None
        self._dual_motion_worker: Poe2DualMotionWorker | None = None
        self._dual_first_frame_worker: Poe2DualFirstFrameWorker | None = None
        self._dual_first_frame_generation = 0
        self._dual_first_frame_pending_recovery = False
        self._dual_first_frame_started_at: float | None = None
        self._retired_dual_first_frame_workers: list[Poe2DualFirstFrameWorker] = []
        self._retired_dual_motion_workers: list[Poe2DualMotionWorker] = []
        self._dual_motion_restart_pending: bool | None = None
        self._dual_motion_session_token = 0
        self._dual_motion_generation = 0
        self._dual_last_ui_render_at = 0.0
        self._dual_frame_failure_suppressed = 0
        self._dual_evidence_count = 0
        self._dual_evidence_signature = None
        self._closing = False
        self._follow_runtime = None
        self._follow_target_display = None
        # The user's last map click is kept separately from simulated and
        # observed positions.  This makes the requested destination visible
        # immediately, even while a follow runtime is waiting for its first
        # tick or before it has been started.
        self._clicked_target_source: tuple[float, float] | None = None
        self._clicked_target_native: tuple[float, float] | None = None
        self._clicked_target_display: tuple[float, float] | None = None
        self._last_follow_observations = {}
        self._follow_program_output = None
        self._follow_role_tracker: CommandRoleTracker | None = None
        self._follow_program_roles: tuple[RoleId, ...] = ()
        self._follow_occluded_roles: tuple[str, ...] = ()
        self._follow_hold_roles: set[str] = set()
        self._follow_rejected_visual: dict[str, int] = {}
        self._follow_leader_role: RoleId | None = None
        self._follow_live_mode = False
        self._follow_visual_phase_grace_ms = 750
        self._follow_sync_phase = "idle"
        self._follow_sync_started_at_ms: int | None = None
        self._follow_sync_baseline_captured_at_ms: int | None = None
        self._follow_sync_frame_count = 0
        self._follow_sync_last_log_at_ms: int | None = None
        self._follow_last_target_log_at_ms: int | None = None
        self._follow_tick_count = 0
        self._follow_tick_attempt_count = 0
        self._follow_session_id: str | None = None
        self._follow_last_program_diagnostics_at_ms: int | None = None
        self._follow_output_write_counts: dict[str, int] = {}
        # A stale visual frame is a transient hold state.  Keep its edge
        # state explicitly so the 100 ms follow timer does not repeatedly
        # release the same output or flood the UI log while capture recovers.
        self._follow_stale_since_ms: int | None = None
        self._follow_stale_release_sent = False
        self._follow_stale_recovery_requested = False
        # Live follow must not arm a virtual controller while the game is
        # behind the workbench.  The Host can accept a report in that state,
        # but PoE2 may not consume it, leaving the visual marker at the old
        # position while command odometry keeps advancing.
        self._follow_game_pid: int | None = None
        self._follow_game_hwnd: int | None = None
        self._follow_foreground_wait_started_ms: int | None = None
        self._follow_foreground_last_log_at_ms: int | None = None
        self._follow_foreground_release_sent = False
        self._follow_foreground_check_override: bool | None = None
        self._follow_foreground_cached_at_ms: int | None = None
        self._follow_foreground_cached_result: tuple[bool, str] | None = None
        self._follow_last_visual_positions: dict[str, tuple[float, float]] = {}
        self._follow_last_visual_at_ms: dict[str, int] = {}
        # A rejected visual observation must be evaluated at most once.  The
        # page timer can tick several times before the worker publishes a new
        # frame; without this per-role timestamp the same failed frame is
        # counted as repeated failures and immediately starts recovery.
        self._follow_last_evaluated_visual_at_ms: dict[str, int] = {}
        # Tests may set this to zero; production keeps the six-second focus
        # handoff window requested for the real game workflow.
        self._follow_command_arm_delay_ms = self._FOLLOW_COMMAND_ARM_DELAY_MS
        self._follow_output_not_before_ms: int | None = None
        self._follow_output_delay_last_log_at_ms: int | None = None
        self._follow_stop_reason: str | None = None
        # Recovery is a non-terminal transition for live follow.  The visual
        # worker may be rebuilt, while the follow timer, runtime, output lease
        # and command predictor continue using bounded estimates.
        self._follow_recovery_pending = False
        self._follow_recovery_retry_scheduled = False
        self._follow_recovery_retry_delay_ms = 0
        # A single visual mismatch must create one recovery episode.  The
        # page-level time cooldown still protects the shared worker, but this
        # session-level edge prevents every follow tick from re-entering the
        # recovery path while the same episode is unresolved.
        self._follow_recovery_episode_active = False
        self._follow_recovery_episode_reason: str | None = None
        self._follow_recovery_episode_suppressed = 0
        self._recovery_controller = RecoveryController()
        self._dual_target_runtime = None
        self._dual_target_output = None
        self._dual_target_roles: tuple[RoleId, ...] = ()
        self._dual_target_observations = {}
        self._dual_target_tick_count = 0
        self._dual_target_last_program_diagnostics_at_ms: int | None = None
        self._dual_target_recovery: tuple[tuple[float, float], str, str, str] | None = None
        self._dual_target_last_recovery_at_ms: int | None = None
        self._dual_recovery_follow_target_source: tuple[float, float] | None = None
        self._dual_recovery_follow_live = False
        self._dual_recovery_follow_instance_id: str | None = None
        self._dual_recovery_follow_radius: float | None = None
        self._dual_recovery_follow_p1: str | None = None
        self._dual_recovery_follow_p2: str | None = None
        self._dual_recovery_follow_mode: str | None = None
        self._program_probe_output = None
        self._program_probe_controller = 1
        self._program_probe_ticks = 0
        self._program_probe_role: RoleId | None = None
        self._program_probe_runtime = None
        self._program_probe_waiting_click = False
        self._program_probe_pending_point: tuple[float, float] | None = None
        self._program_probe_game_pid: int | None = None
        self._program_probe_game_hwnd: int | None = None
        self._program_probe_started_at_ms: int | None = None
        self._program_probe_initial_position: tuple[float, float] | None = None
        self._program_probe_last_position: tuple[float, float] | None = None
        self._program_probe_target: tuple[float, float] | None = None
        self._program_probe_last_observation = None
        # A contact recovery is a state transition, not a terminal stop. Keep
        # the original destination and controller selection while the dual
        # first-frame pipeline performs its one-shot memory re-anchor.
        self._program_probe_recovery_target: tuple[float, float] | None = None
        self._program_probe_recovery_identity: str | None = None
        self._program_probe_recovery_controller: int | None = None
        self._program_probe_recovery_started_at_ms: int | None = None
        self._program_probe_recovery_attempts = 0
        self._program_probe_last_relocalization_at_ms: int | None = None
        self._program_probe_arm_timer = QTimer(self)
        self._program_probe_arm_timer.setSingleShot(True)
        self._program_probe_arm_timer.timeout.connect(self._arm_program_move_probe)
        self._program_probe_timer = QTimer(self)
        self._program_probe_timer.setInterval(50)
        self._program_probe_timer.timeout.connect(self._tick_program_move_probe)
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(100)
        self._follow_timer.timeout.connect(self._tick_follow_experiment)
        self._dual_target_timer = QTimer(self)
        self._dual_target_timer.setInterval(100)
        self._dual_target_timer.timeout.connect(self._tick_dual_target_experiment)
        self._dual_motion_timer = QTimer(self)
        self._dual_motion_timer.setInterval(self._localization_interval())
        self._dual_motion_timer.timeout.connect(self._tick_dual_motion)
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory: list[tuple[float, float]] = []
        self._multiframe_trajectory_version = 0
        self._multiframe_timer = QTimer(self)
        self._multiframe_timer.setInterval(self._localization_interval())
        self._multiframe_timer.timeout.connect(self._tick_multiframe)
        self.localization_control_dialog = Poe2LocalizationControlDialog(self)
        self.multiframe_panel = self.localization_control_dialog.panel
        self._build_ui()
        self._log_handler = _UiLogHandler(self)
        self._log_handler.message_emitted.connect(self._append_session_log)
        self._logger.addHandler(self._log_handler)
        self._append_session_log("PoE2 实验会话已创建")
        self._render_state("未初始化")

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        workspace = QWidget(self)
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)

        sidebar = QWidget(self)
        sidebar_root = QVBoxLayout(sidebar)
        sidebar_root.setContentsMargins(0, 0, 0, 0)
        sidebar_root.setSpacing(6)
        self.stop_all_program_button = QPushButton("停止全部程序移动")
        self.stop_all_program_button.setToolTip("释放本实验页的定点移动、双人同目标和跟随手柄输出")
        self.stop_all_program_button.clicked.connect(self.stop_all_program_motion)
        sidebar_root.addWidget(self.stop_all_program_button)
        self.sidebar_tabs = QTabWidget(sidebar)
        sidebar_root.addWidget(self.sidebar_tabs, 1)

        def scroll_tab(title: str):
            scroll = QScrollArea(self.sidebar_tabs)
            scroll.setWidgetResizable(True)
            content = QWidget(scroll)
            layout = QVBoxLayout(content)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)
            scroll.setWidget(content)
            self.sidebar_tabs.addTab(scroll, title)
            return layout

        capture_layout = scroll_tab("采集定位")
        motion_layout = scroll_tab("移动跟随")
        log_layout = scroll_tab("日志")

        controls_group = QGroupBox("地图与截图")
        controls = QGridLayout(controls_group)
        controls.setHorizontalSpacing(6)
        controls.setVerticalSpacing(6)
        self.monitor_config_button = QPushButton("监控配置")
        self.capture_monitor_button = QPushButton("打开截图监控窗口")
        self.refresh_preview_button = QPushButton("刷新截图")
        self.start_preview_button = QPushButton("开始截图监控")
        self.stop_preview_button = QPushButton("停止截图监控")
        self.initialize_button = QPushButton("初始化")
        self.capture_button = QPushButton("获取当前地图")
        self.save_button = QPushButton("保存当前地图")
        self.reset_button = QPushButton("清空测试状态")
        self.start_single_frame_button = QPushButton("开始首帧定位")
        self.stop_single_frame_button = QPushButton("停止首帧定位")
        self.dual_first_frame_button = QPushButton("双人首帧实验")
        self.start_dual_motion_button = QPushButton("开始双人实时定位")
        self.stop_dual_motion_button = QPushButton("停止双人实时定位")
        self.localization_control_button = QPushButton("定位控制")
        self.monitor_config_button.clicked.connect(self._open_config)
        self.capture_monitor_button.clicked.connect(self.open_capture_monitor)
        self.refresh_preview_button.clicked.connect(self.refresh_preview)
        self.start_preview_button.clicked.connect(self.start_preview)
        self.stop_preview_button.clicked.connect(self.stop_preview)
        self.initialize_button.clicked.connect(self.initialize_session)
        self.capture_button.clicked.connect(self.capture_map)
        self.save_button.clicked.connect(self.save_map)
        self.reset_button.clicked.connect(self.reset_session)
        self.start_single_frame_button.clicked.connect(self.start_hybrid_localization)
        self.stop_single_frame_button.clicked.connect(self.stop_hybrid_localization)
        self.dual_first_frame_button.clicked.connect(lambda: self.run_dual_first_frame_experiment())
        self.start_dual_motion_button.clicked.connect(self.start_dual_motion)
        self.stop_dual_motion_button.clicked.connect(self.stop_dual_motion)
        self.localization_control_button.clicked.connect(self.open_localization_control)
        for row, pair in enumerate((
            (self.initialize_button, self.capture_button),
            (self.start_preview_button, self.stop_preview_button),
            (self.refresh_preview_button, self.capture_monitor_button),
            (self.monitor_config_button, self.save_button),
        )):
            for column, button in enumerate(pair):
                controls.addWidget(button, row, column)
        controls.addWidget(self.reset_button, 4, 0, 1, 2)
        capture_layout.addWidget(controls_group)

        single_group = QGroupBox("单人定位")
        single_controls = QGridLayout(single_group)
        single_controls.addWidget(self.start_single_frame_button, 0, 0)
        single_controls.addWidget(self.stop_single_frame_button, 0, 1)
        single_controls.addWidget(self.localization_control_button, 1, 0, 1, 2)
        capture_layout.addWidget(single_group)

        self.status_label = QLabel()
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.archive_label = QLabel("尚未保存地图")
        self.archive_label.setWordWrap(True)
        self.metadata_label = QLabel("尚未获取地图")
        self.metadata_label.setWordWrap(True)
        self.player_position_label = QLabel("人物位置：未读取")
        self.player_position_label.setWordWrap(True)
        self.single_frame_status_label = QLabel("首帧定位：未启动")
        self.single_frame_status_label.setWordWrap(True)
        self.dual_first_frame_status_label = QLabel("双人首帧：未启动")
        self.dual_first_frame_status_label.setWordWrap(True)
        self.dual_motion_status_label = QLabel("双人实时：未启动")
        self.dual_motion_status_label.setWordWrap(True)
        status_group = QGroupBox("当前状态")
        status_layout = QVBoxLayout(status_group)
        for label in (
            self.status_label,
            self.error_label,
            self.archive_label,
            self.metadata_label,
            self.player_position_label,
            self.single_frame_status_label,
            self.dual_first_frame_status_label,
            self.dual_motion_status_label,
        ):
            status_layout.addWidget(label)

        follow_group = QGroupBox("自动跟随实验")
        follow_layout = QVBoxLayout(follow_group)
        follow_controls = QVBoxLayout()
        self.follow_mode_combo = QComboBox()
        self.follow_mode_combo.addItem("P1 + P2 模拟（不发手柄）", "both")
        self.follow_mode_combo.addItem("P1 手动 / P2 模拟", "p1_manual")
        self.follow_mode_combo.addItem("单人 P1 程序控制（真实手柄）", "single_p1_program")
        self.follow_mode_combo.addItem("单人 P2 程序控制（真实手柄）", "single_p2_program")
        self.follow_mode_combo.addItem("P1 + P2 程序控制（真实手柄）", "both_program")
        self.follow_mode_combo.addItem("P1 手动 / P2 实时跟随", "p1_leads")
        self.follow_mode_combo.addItem("P2 手动 / P1 实时跟随", "p2_leads")
        self.follow_mode_combo.currentIndexChanged.connect(self._sync_follow_radius_control)
        self.follow_p1_combo = QComboBox()
        self.follow_p2_combo = QComboBox()
        self.follow_p1_combo.addItem("选择 P1 角色", None)
        self.follow_p2_combo.addItem("选择 P2 角色", None)
        self.start_follow_button = QPushButton("开始跟随实验")
        self.stop_follow_button = QPushButton("停止跟随实验")
        self.start_follow_button.clicked.connect(self.start_follow_experiment)
        self.stop_follow_button.clicked.connect(self.stop_follow_experiment)
        follow_controls.addWidget(self.follow_mode_combo)
        follow_controls.addWidget(self.follow_p1_combo)
        follow_controls.addWidget(self.follow_p2_combo)
        radius_row = QHBoxLayout()
        self.follow_radius_label = QLabel("实时跟随人物半径")
        radius_row.addWidget(self.follow_radius_label)
        self.follow_footprint_radius = QDoubleSpinBox()
        self.follow_footprint_radius.setRange(0.0, 12.0)
        self.follow_footprint_radius.setSingleStep(0.5)
        self.follow_footprint_radius.setValue(3.0)
        self.follow_footprint_radius.setToolTip("原始地图格单位；用于贴墙路线校验与恢复，不膨胀墙体")
        radius_row.addWidget(self.follow_footprint_radius)
        follow_controls.addLayout(radius_row)
        follow_actions = QHBoxLayout()
        follow_actions.addWidget(self.start_follow_button)
        follow_actions.addWidget(self.stop_follow_button)
        follow_controls.addLayout(follow_actions)
        follow_layout.addLayout(follow_controls)
        self.follow_status_label = QLabel("跟随实验：先启动双人实时定位，再点击下方地图设置共享目标")
        self.follow_status_label.setWordWrap(True)
        follow_layout.addWidget(self.follow_status_label)
        motion_layout.addWidget(follow_group)
        self.start_follow_button.setEnabled(False)
        self.stop_follow_button.setEnabled(False)
        self._sync_follow_radius_control()

        target_group = QGroupBox("双人同目标移动实验（真实手柄）")
        target_layout = QVBoxLayout(target_group)
        self.dual_target_p1_combo = QComboBox()
        self.dual_target_p2_combo = QComboBox()
        self.dual_target_p1_combo.addItem("选择 P1 角色", None)
        self.dual_target_p2_combo.addItem("选择 P2 角色", None)
        target_layout.addWidget(self.dual_target_p1_combo)
        target_layout.addWidget(self.dual_target_p2_combo)
        target_actions = QHBoxLayout()
        self.start_dual_target_button = QPushButton("准备双人目标")
        self.stop_dual_target_button = QPushButton("立即停止")
        self.start_dual_target_button.clicked.connect(self.start_dual_target_experiment)
        self.stop_dual_target_button.clicked.connect(self.stop_dual_target_experiment)
        target_actions.addWidget(self.start_dual_target_button)
        target_actions.addWidget(self.stop_dual_target_button)
        target_layout.addLayout(target_actions)
        self.dual_target_status_label = QLabel("双人同目标：未启动")
        self.dual_target_status_label.setWordWrap(True)
        target_layout.addWidget(self.dual_target_status_label)
        motion_layout.addWidget(target_group)
        self.start_dual_target_button.setEnabled(False)
        self.stop_dual_target_button.setEnabled(False)

        dual_group = QGroupBox("双人定位")
        dual_controls = QVBoxLayout(dual_group)
        dual_controls.addWidget(self.dual_first_frame_button)
        budget_row = QHBoxLayout()
        budget_row.addWidget(QLabel("失明宽限(秒)"))
        self.dual_marker_hold_seconds = QDoubleSpinBox()
        self.dual_marker_hold_seconds.setRange(0.2, 5.0)
        self.dual_marker_hold_seconds.setSingleStep(0.2)
        self.dual_marker_hold_seconds.setValue(2.0)
        self.dual_marker_hold_seconds.setToolTip("只在墙层持续可信时生效；下次启动定位时应用")
        budget_row.addWidget(self.dual_marker_hold_seconds)
        budget_row.addWidget(QLabel("误差上限(格)"))
        self.dual_marker_error_limit = QDoubleSpinBox()
        self.dual_marker_error_limit.setRange(1.0, 30.0)
        self.dual_marker_error_limit.setSingleStep(1.0)
        self.dual_marker_error_limit.setValue(10.0)
        self.dual_marker_error_limit.setToolTip("最后可信人物位置的最大估计误差；下次启动定位时应用")
        budget_row.addWidget(self.dual_marker_error_limit)
        dual_controls.addLayout(budget_row)
        dual_controls.addWidget(self.start_dual_motion_button)
        dual_controls.addWidget(self.stop_dual_motion_button)
        capture_layout.addWidget(dual_group)
        capture_layout.addWidget(status_group)
        self.stop_dual_motion_button.setEnabled(False)

        probe_group = QGroupBox("地图点移动实验（真实手柄）")
        probe_layout = QVBoxLayout(probe_group)
        self.program_probe_role_combo = QComboBox()
        self.program_probe_role_combo.addItem("选择移动角色", None)
        self.program_probe_controller_combo = QComboBox()
        self.program_probe_controller_combo.addItem("P1 / 控制器 1", 1)
        self.program_probe_controller_combo.addItem("P2 / 控制器 2", 2)
        self.program_probe_button = QPushButton("准备点击目标")
        self.program_probe_button.clicked.connect(self.start_program_move_probe)
        self.program_probe_stop_button = QPushButton("立即停止")
        self.program_probe_stop_button.clicked.connect(self.stop_program_move_probe)
        self.program_probe_status_label = QLabel("未发送真实输入")
        self.program_probe_status_label.setWordWrap(True)
        probe_layout.addWidget(self.program_probe_role_combo)
        probe_layout.addWidget(self.program_probe_controller_combo)
        probe_actions = QHBoxLayout()
        probe_actions.addWidget(self.program_probe_button)
        probe_actions.addWidget(self.program_probe_stop_button)
        probe_layout.addLayout(probe_actions)
        probe_layout.addWidget(self.program_probe_status_label)
        motion_layout.addWidget(probe_group)
        self.program_probe_stop_button.setEnabled(False)

        hybrid_group = QGroupBox("混合定位实验")
        self._legacy_hybrid_group = hybrid_group
        hybrid_layout = QVBoxLayout(hybrid_group)
        hybrid_controls = QHBoxLayout()
        self.start_hybrid_button = QPushButton("开始混合定位")
        self.stop_hybrid_button = QPushButton("停止")
        self.retry_hybrid_button = QPushButton("重新恢复一次")
        self.start_hybrid_button.clicked.connect(self.start_hybrid_localization)
        self.stop_hybrid_button.clicked.connect(self.stop_hybrid_localization)
        self.retry_hybrid_button.clicked.connect(self.retry_hybrid_recovery)
        hybrid_controls.addWidget(self.start_hybrid_button)
        hybrid_controls.addWidget(self.stop_hybrid_button)
        hybrid_controls.addWidget(self.retry_hybrid_button)
        hybrid_controls.addStretch()
        hybrid_layout.addLayout(hybrid_controls)
        self.hybrid_status_label = QLabel("混合定位：未启动")
        self.hybrid_status_label.setWordWrap(True)
        self.hybrid_position_label = QLabel("实时位置：暂无")
        hybrid_layout.addWidget(self.hybrid_status_label)
        hybrid_layout.addWidget(self.hybrid_position_label)
        hybrid_group.setVisible(False)
        capture_layout.addWidget(hybrid_group)

        self.multiframe_panel.start_requested.connect(self.start_multiframe_localization)
        self.multiframe_panel.stop_requested.connect(self.stop_multiframe_localization)
        self.multiframe_panel.reset_requested.connect(self.reset_multiframe_localization)
        self.multiframe_panel.save_requested.connect(self.save_multiframe_experiment)
        self.start_multiframe_button = self.multiframe_panel.start_button
        self.stop_multiframe_button = self.multiframe_panel.stop_button
        self.multiframe_status_label = self.multiframe_panel.status_label
        self.multiframe_position_label = self.multiframe_panel.position_label

        preview_group = QGroupBox("小地图截图与视觉特征")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_splitter = QSplitter(Qt.Horizontal, preview_group)
        self.frame_preview_panel, self.frame_preview = self._make_preview("当前截图")
        self.processed_preview_panel, self.processed_preview = self._make_preview("预处理画面")
        self.feature_preview_panel, self.feature_preview = self._make_preview("匹配特征")
        for panel in (self.frame_preview_panel, self.processed_preview_panel, self.feature_preview_panel):
            self.preview_splitter.addWidget(panel)
        self.preview_splitter.setChildrenCollapsible(False)
        preview_layout.addWidget(self.preview_splitter)

        map_group = QGroupBox("当前获取的地图")
        map_layout = QVBoxLayout(map_group)
        self.map_widget = ScalableMapWidget(self)
        self.map_widget.pixel_clicked.connect(self._on_follow_map_click)
        self.map_widget.fit_scale_multiplier = 1.35
        map_layout.addWidget(self.map_widget)
        self.workspace_splitter = QSplitter(Qt.Vertical, workspace)
        self.workspace_splitter.addWidget(preview_group)
        self.workspace_splitter.addWidget(map_group)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.workspace_splitter.setStretchFactor(0, 1)
        self.workspace_splitter.setStretchFactor(1, 4)
        self.workspace_splitter.setSizes([300, 500])
        workspace_layout.addWidget(self.workspace_splitter)

        log_group = QGroupBox("本次实验日志")
        log_group_layout = QVBoxLayout(log_group)
        log_header = QHBoxLayout()
        log_header.addStretch()
        self.clear_log_button = QPushButton("清空")
        self.clear_log_button.clicked.connect(lambda: self.session_log.clear())
        log_header.addWidget(self.clear_log_button)
        log_group_layout.addLayout(log_header)
        self.session_log = QPlainTextEdit()
        self.session_log.setReadOnly(True)
        self.session_log.setMaximumBlockCount(500)
        self.session_log.setMinimumHeight(220)
        self.session_log.setPlaceholderText("初始化、定位、程序输出和 Host 状态会显示在这里")
        log_group_layout.addWidget(self.session_log, 1)
        log_layout.addWidget(log_group, 1)
        capture_layout.addStretch()
        motion_layout.addStretch()

        self.main_splitter = QSplitter(Qt.Horizontal, self)
        self.main_splitter.addWidget(workspace)
        self.main_splitter.addWidget(sidebar)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 1)
        sidebar.setMinimumWidth(300)
        self.main_splitter.setSizes([900, 380])
        root.addWidget(self.main_splitter)
        self.stop_preview_button.setEnabled(False)
        self.stop_single_frame_button.setEnabled(False)
        self.dual_first_frame_button.setEnabled(False)
        self.start_hybrid_button.setEnabled(False)
        self.stop_hybrid_button.setEnabled(False)
        self.retry_hybrid_button.setEnabled(False)
        self.start_multiframe_button.setEnabled(False)
        self.stop_multiframe_button.setEnabled(False)

    @staticmethod
    def _make_preview(title: str):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 2, 2, 2)
        title_label = QLabel(title)
        title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(title_label)
        label = AspectPreviewLabel("尚未截图")
        label.setMinimumSize(220, 220)
        label.setStyleSheet("background: #101318; border: 1px solid #39414d;")
        layout.addWidget(label, 1)
        return panel, label

    def set_monitor_config(self, config: Any) -> None:
        self.monitor_config = config
        self.preview_timer.setInterval(self._preview_interval())
        self.hybrid_timer.setInterval(self._localization_interval())
        self._dual_motion_timer.setInterval(self._localization_interval())
        self._multiframe_timer.setInterval(self._localization_interval())
        if self.capture_monitor_window is not None:
            self.capture_monitor_window.preview_timer.setInterval(self._preview_interval())

    def open_capture_monitor(self) -> None:
        if (
            self.sample_archive is None
            or self.stitching_session_factory is None
            or self.stitching_archive is None
            or self.preview_provider is None
            or self.recognizer is None
        ):
            self._show_error(RuntimeError("截图监控窗口依赖未完整注入"))
            return
        if self.capture_monitor_window is None:
            self.capture_monitor_window = Poe2CaptureMonitorWindow(
                preview_provider=self.preview_provider,
                recognizer=self.recognizer,
                monitor_config_provider=lambda: self.monitor_config,
                terrain_snapshot_provider=self.service.snapshot,
                sample_archive=self.sample_archive,
                stitching_session=self.stitching_session_factory(),
                stitching_archive=self.stitching_archive,
                player_position_provider=lambda: self._player_position,
                parent=self,
            )
            if self._last_hybrid_state is not None:
                self.capture_monitor_window.handle_hybrid_state(
                    self._last_hybrid_state,
                    read_count=self._hybrid_read_count(),
                )
        self.capture_monitor_window.show()
        self.capture_monitor_window.raise_()
        self.capture_monitor_window.activateWindow()

    def _sample_interval(self) -> int:
        return max(20, int(getattr(self.monitor_config, "sample_interval_ms", 100)))

    def _localization_interval(self) -> int:
        """Return the effective visual localization period.

        ``sample_interval_ms`` predates the explicit FPS controls and remains
        an upper bound for compatibility.  The localization FPS must still
        take effect; otherwise the default 100 ms silently caps a configured
        30 FPS session at roughly 10 FPS.
        """
        requested_fps = max(1, int(getattr(self.monitor_config, "localization_fps", 30)))
        target_interval = round(1000 / requested_fps)
        return max(20, min(self._sample_interval(), target_interval))

    def _preview_interval(self) -> int:
        """Return the lower-priority preview period without throttling tracking."""
        requested_fps = max(1, int(getattr(self.monitor_config, "preview_fps", 12)))
        target_interval = round(1000 / requested_fps)
        return max(20, max(self._sample_interval(), target_interval))

    def _open_config(self) -> None:
        if self.open_config_callback is None:
            self._show_error(RuntimeError("PoE2 监控配置入口未注入"))
            return
        self.open_config_callback()

    def open_localization_control(self) -> None:
        """Show experiment controls without shrinking the capture/map workspace."""
        self.localization_control_dialog.set_ready(
            self._snapshot is not None and self.multiframe_localization_factory is not None
        )
        self.localization_control_dialog.show_non_modal()

    def initialize_session(self) -> None:
        self._logger.info("step=test_page.initialize_clicked")
        self._clear_map_state()
        try:
            self.service.initialize()
        except Exception as exc:
            self._logger.exception("step=test_page.initialize_failed error=%s", exc)
            self._show_error(exc)
            return
        self.error_label.clear()
        self._render_state("可获取当前地图")
        self._logger.info("step=test_page.initialize_success")

    def capture_map(self) -> None:
        self._logger.info("step=test_page.capture_clicked")
        self._invalidate_dual_motion_session()
        self.stop_program_move_probe()
        self.stop_dual_motion()
        self._sync_follow_role_choices({})
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self._last_dual_first_frame_result = None
        self._dual_first_frame_read_count = 0
        self._dual_initial_frame = None
        self._dual_initial_candidates = ()
        self._dual_preview_active = False
        self.dual_first_frame_status_label.setText("双人首帧：未启动")
        self._hybrid_experiment = None
        self._last_hybrid_state = None
        try:
            snapshot = self.service.capture()
        except Exception as exc:
            self._logger.exception("step=test_page.capture_failed error=%s", exc)
            self._clear_map_state()
            self._show_error(exc)
            return
        self._snapshot = snapshot
        player_position: PlayerPositionSample | None = None
        position_error = None
        if self.player_position_source is not None:
            self._logger.info("step=test_page.player_position_start instance=%s", snapshot.metadata.instance_id)
            try:
                reader = getattr(self.player_position_source, "read_once", None)
                if not callable(reader):
                    raise RuntimeError("人物位置读取器未提供 read_once")
                sample = reader(snapshot.metadata.instance_id)
                grid = getattr(sample, "grid", None)
                if grid is None or len(grid) != 2:
                    raise RuntimeError("人物位置读取器返回了无效坐标")
                player_position = cast("PlayerPositionSample", sample)
            except Exception as exc:
                position_error = exc
                self._logger.exception("step=test_page.player_position_failed error=%s", exc)
            else:
                self._logger.info(
                    "step=test_page.player_position_success grid=(%.2f, %.2f)",
                    grid[0],
                    grid[1],
                )
        self._player_position = player_position
        display = present_snapshot(
            snapshot,
            orientation=self._map_orientation(),
            player_position=player_position,
        )
        self._terrain_base_pixmap = display.pixmap
        self.map_widget.set_image(display.pixmap)
        if player_position is not None:
            orientation = self._map_orientation()
            point = orientation.transform_point(
                player_position.grid,
                (snapshot.metadata.height, snapshot.metadata.width),
            )
            point = localization_display_point(
                point,
                source_size=(display.pixmap.width(), display.pixmap.height()),
            )
            self.map_widget.focus_on_point(
                point,
                zoom_multiplier=self.map_follow_zoom_multiplier,
            )
        self.metadata_label.setText("\n".join(display.metadata_lines))
        if player_position is not None:
            self.player_position_label.setText(
                f"人物位置：网格 ({player_position.grid[0]:.2f}, {player_position.grid[1]:.2f})"
            )
        elif self.player_position_source is None:
            self.player_position_label.setText("人物位置：未注入读取器")
        else:
            self.player_position_label.setText("人物位置：读取失败")
        if position_error is None:
            self.error_label.clear()
            self._render_state("已获取当前地图")
        else:
            self.error_label.setText(f"人物定位错误（地图仍已获取）：{position_error}")
            self._render_state("已获取当前地图，人物定位失败")
        self._logger.info("step=test_page.capture_success instance=%s", snapshot.metadata.instance_id)

    def _compute_dual_first_frame(
        self,
        snapshot: Any,
        *,
        recognizer: Any,
        preview_provider: Callable[[Any], Any],
        force_memory_read: bool,
    ) -> Any:
        """Compute one dual registration without touching Qt widgets."""
        captured_at_ms = int(time.time() * 1000)
        self._logger.info(
            "step=dual_first_frame.compute_started instance=%s captured_at_ms=%s "
            "force_memory_read=%s",
            snapshot.metadata.instance_id, captured_at_ms, force_memory_read,
        )
        orientation = self._map_orientation()
        source = self.dual_player_position_source or Poe2DualPlayerPositionSource()
        anchor_provider = Poe2DualMemoryAnchorProvider(
            source, orientation, (snapshot.metadata.height, snapshot.metadata.width),
        )
        experiment = (
            self.dual_first_frame_factory(anchor_provider)
            if self.dual_first_frame_factory is not None
            else DualFirstFrameExperiment(
                anchor_provider,
                registrar=build_poe2_dual_first_frame_registrar(self.monitor_config),
            )
        )
        anchors = experiment.read_anchors(snapshot.metadata.instance_id)
        self._logger.info(
            "step=dual_first_frame.memory_success read_count=%s identities=%s anchors=%s",
            anchor_provider.read_count, tuple(anchors),
            {identity: anchor.position for identity, anchor in anchors.items()},
        )
        configured_profiles = getattr(self.monitor_config, "dual_marker_profiles", ())
        profiles = tuple(MarkerColorProfile.from_dict(item) for item in configured_profiles)
        captured_frames = []
        capture_attempts = 3
        for attempt in range(1, capture_attempts + 1):
            candidate_frame = preview_provider(self.monitor_config)
            if candidate_frame is None:
                self._logger.warning(
                    "step=dual_first_frame.capture_empty attempt=%s/%s",
                    attempt, capture_attempts,
                )
            else:
                candidate_combined = recognizer.extract_combined(
                    candidate_frame, player_pos=None,
                    exclude_player=False, exclude_dynamic=False,
                )
                candidate_mask = (
                    candidate_combined[0]
                    if isinstance(candidate_combined, (tuple, list))
                    else candidate_combined
                )
                candidate_captured_at_ms = int(time.time() * 1000)
                candidate_observation = detect_saturated_marker_observation(
                    candidate_frame, candidate_captured_at_ms,
                    profiles=profiles or None,
                )
                captured_frames.append({
                    "raw": candidate_frame,
                    "combined": candidate_combined,
                    "mask": candidate_mask,
                    "observation": candidate_observation,
                    "captured_at_ms": candidate_captured_at_ms,
                })
                self._logger.info(
                    "step=dual_first_frame.capture_success attempt=%s/%s shape=%s",
                    attempt, capture_attempts, getattr(candidate_frame, "shape", None),
                )
                self._logger.info(
                    "step=dual_first_frame.observation attempt=%s/%s candidates=%s positions=%s",
                    attempt, capture_attempts, len(candidate_observation.candidates),
                    [candidate.local_position for candidate in candidate_observation.candidates],
                )
            if attempt < capture_attempts:
                time.sleep(0.04)
        if not captured_frames:
            raise RuntimeError("截图后端返回空帧")
        reference = orientation.transform_reference(build_reference(snapshot))
        registrations = []
        for captured in captured_frames:
            match_mask = captured["mask"]
            frame_array = getattr(match_mask, "shape", None)
            if frame_array is None or len(frame_array) != 2 or any(
                int(size) <= 0 for size in frame_array
            ):
                self._logger.warning(
                    "step=dual_first_frame.candidate_rejected reason=invalid_mask_shape shape=%s",
                    frame_array,
                )
                continue
            frame = HybridFrame(
                frame_id=int(captured["captured_at_ms"]),
                captured_at_ms=int(captured["captured_at_ms"]),
                wall_mask=match_mask,
                local_player=(float(frame_array[1]) / 2.0, float(frame_array[0]) / 2.0),
                diagnostics={
                    "capture_size": max(int(frame_array[0]), int(frame_array[1])),
                    "mode": "dual_first_frame",
                    "capture_attempt": len(registrations) + 1,
                },
            )
            try:
                candidate_result = experiment.register(
                    frame, reference=reference, anchors=anchors,
                    observation=captured["observation"],
                )
            except Exception:
                self._logger.exception(
                    "step=dual_first_frame.candidate_register_failed attempt=%s",
                    len(registrations) + 1,
                )
                continue
            diagnostics = dict(getattr(candidate_result, "diagnostics", {}) or {})
            registrations.append((candidate_result, captured, frame, diagnostics))
            self._logger.info(
                "step=dual_first_frame.candidate_result attempt=%s status=%s score=%s "
                "pair_confidence=%s shape_quality=%s",
                len(registrations), getattr(candidate_result, "status", None),
                diagnostics.get("best_pair_confidence", diagnostics.get("best_score")),
                diagnostics.get("best_pair_confidence"),
                diagnostics.get("best_shape_quality", diagnostics.get("best_forward_coverage")),
            )
        if not registrations:
            raise RuntimeError("所有首帧截图都无法生成有效匹配候选")

        def registration_key(item):
            candidate_result, _captured, _frame, diagnostics = item
            accepted = getattr(candidate_result, "status", None) == "accepted"
            return (
                1 if accepted else 0,
                float(diagnostics.get("best_pair_confidence", 0.0) or 0.0),
                float(diagnostics.get("best_shape_quality", diagnostics.get("best_forward_coverage", 0.0)) or 0.0),
                -float(diagnostics.get("best_mean_anchor_error", float("inf")) or float("inf")),
            )

        result, selected, frame, _diagnostics = max(registrations, key=registration_key)
        self._logger.info(
            "step=dual_first_frame.consensus_selected candidates=%s selected_attempt=%s status=%s",
            len(registrations), int(frame.diagnostics.get("capture_attempt", 0)),
            getattr(result, "status", None),
        )
        return SimpleNamespace(
            result=result,
            frame=frame,
            observation=selected["observation"],
            raw_frame=selected["raw"],
            combined=selected["combined"],
            read_count=anchor_provider.read_count,
        )

    def _apply_dual_first_frame_bundle(self, bundle: Any, *, render_map: bool) -> None:
        result = bundle.result
        self._dual_first_frame_read_count = int(bundle.read_count)
        self._last_dual_first_frame_result = result
        self._dual_initial_frame = bundle.frame if result.accepted else None
        self._dual_initial_candidates = (
            marker_candidates_from_observation(bundle.observation, max_candidates=6)
            if result.accepted else ()
        )
        self._dual_preview_active = True
        self._render_preview(bundle.raw_frame, combined=bundle.combined)
        self._render_dual_first_frame_result(result, self._snapshot, render_map=render_map)
        self._logger.info(
            "step=dual_first_frame.result status=%s reason=%s diagnostics=%s players=%s",
            result.status, result.reason, dict(result.diagnostics),
            result.as_dict().get("players", {}),
        )

    def run_dual_first_frame_experiment(
        self, *, render_map: bool = True, force_memory_read: bool = False,
    ) -> None:
        """Run one dual registration synchronously for the manual lab button."""
        if self._snapshot is None:
            self._show_error(RuntimeError("请先获取当前地图"))
            return
        if self._dual_motion_timer.isActive():
            self.stop_dual_motion()
        self._last_dual_first_frame_result = None
        self._dual_initial_frame = None
        self._dual_initial_candidates = ()
        if self.preview_provider is None or self.recognizer is None:
            self._show_error(RuntimeError("双人首帧实验需要截图和识别后端"))
            return
        snapshot = self._snapshot
        self.dual_first_frame_status_label.setText("双人首帧：正在读取人物锚点")
        try:
            bundle = self._compute_dual_first_frame(
                snapshot, recognizer=self.recognizer,
                preview_provider=self.preview_provider,
                force_memory_read=force_memory_read,
            )
            self._apply_dual_first_frame_bundle(bundle, render_map=render_map)
        except Exception as exc:
            self._logger.exception("step=dual_first_frame.failed")
            self.dual_first_frame_status_label.setText(f"双人首帧：失败 | {exc}")
            self._show_error(exc)

    def start_dual_motion(self) -> None:
        """Start a separate two-player visual experiment after one memory read."""
        self._dual_last_recovery_at_ms = None
        self._start_dual_motion(recovery=False)

    def _clone_dual_worker_recognizer(self) -> Any | None:
        if self.recognizer is None:
            return None
        get_params = getattr(self.recognizer, "get_params", None)
        set_params = getattr(self.recognizer, "set_params", None)
        if not callable(get_params) or not callable(set_params):
            return None
        try:
            candidate = type(self.recognizer)()
            candidate.set_params(dict(get_params()))
            return candidate
        except Exception:
            self._logger.exception("step=dual_motion.worker_recognizer_clone_failed")
            return None

    def _start_dual_first_frame_async(self, *, recovery: bool) -> bool:
        """Submit a recovery registration without blocking the Qt event loop."""
        if self._dual_first_frame_worker is not None:
            if getattr(self._dual_first_frame_worker, "is_running", False):
                self.dual_motion_status_label.setText("双人实时：正在后台恢复定位")
                return True
            self._dual_first_frame_worker = None
        if self._snapshot is None or self.preview_provider is None or self.recognizer is None:
            return False
        worker_recognizer = self._clone_dual_worker_recognizer()
        if worker_recognizer is None:
            self._logger.warning(
                "step=dual_motion.recovery_worker_unavailable reason=recognizer_not_isolated"
            )
            return False
        self._dual_first_frame_generation += 1
        generation = self._dual_first_frame_generation
        snapshot = self._snapshot
        preview_provider = self.preview_provider
        cleanup = getattr(preview_provider, "close_current_thread", None)
        worker = Poe2DualFirstFrameWorker(
            task=lambda: self._compute_dual_first_frame(
                snapshot,
                recognizer=worker_recognizer,
                preview_provider=preview_provider,
                force_memory_read=True,
            ),
            generation=generation,
            cleanup=cleanup if callable(cleanup) else None,
        )
        worker.result_available.connect(self._on_dual_first_frame_worker_result)
        worker.failed.connect(self._on_dual_first_frame_worker_failed)
        worker.finished.connect(self._on_dual_first_frame_worker_finished)
        self._dual_first_frame_worker = worker
        self._dual_first_frame_pending_recovery = bool(recovery)
        self._dual_first_frame_started_at = time.perf_counter()
        self.start_dual_motion_button.setEnabled(False)
        self.stop_dual_motion_button.setEnabled(False)
        self.dual_first_frame_status_label.setText("双人首帧：后台恢复定位中")
        self.dual_motion_status_label.setText("双人实时：后台恢复定位中，界面保持响应")
        self._logger.info(
            "step=dual_first_frame.worker_started generation=%s recovery=%s",
            generation, recovery,
        )
        worker.start()
        return True

    def _on_dual_first_frame_worker_result(self, generation: int, bundle: Any) -> None:
        if (
            self._closing
            or generation != self._dual_first_frame_generation
            or self._dual_first_frame_worker is None
        ):
            return
        recovery = self._dual_first_frame_pending_recovery
        self._dual_first_frame_pending_recovery = False
        worker = self._dual_first_frame_worker
        self._dual_first_frame_worker = None
        if worker is not None and worker not in self._retired_dual_first_frame_workers:
            self._retired_dual_first_frame_workers.append(worker)
        try:
            self._apply_dual_first_frame_bundle(bundle, render_map=False)
            self._logger.info(
                "step=dual_first_frame.worker_result generation=%s status=%s accepted=%s "
                "recovery=%s elapsed_ms=%.1f",
                generation, bundle.result.status, bundle.result.accepted,
                recovery,
                (time.perf_counter() - self._dual_first_frame_started_at) * 1000.0
                if self._dual_first_frame_started_at is not None else -1.0,
            )
            self._dual_first_frame_started_at = None
            if recovery and bundle.result.accepted:
                self._start_dual_motion(
                    recovery=True,
                    first_frame_ready=True,
                    preserve_follow=self._follow_recovery_pending,
                )
            elif recovery:
                self._logger.error(
                    "step=program_probe.relocalization_failed reason=first_frame_rejected"
                )
                if not self._follow_recovery_pending:
                    self._clear_dual_recovery_contexts()
                else:
                    self._logger.warning(
                        "step=dual_motion.recovery_deferred reason=first_frame_rejected "
                        "follow_prediction_continues=True",
                    )
                    self._schedule_live_follow_recovery_retry("first_frame_rejected")
                self.start_dual_motion_button.setEnabled(self._snapshot is not None)
        except Exception as exc:
            self._logger.exception("step=dual_first_frame.worker_apply_failed error=%s", exc)
            if self._follow_recovery_pending:
                self._logger.warning(
                    "step=dual_motion.recovery_deferred reason=worker_apply_failed "
                    "follow_prediction_continues=True error=%s",
                    exc,
                )
                self.dual_motion_status_label.setText(
                    "双人实时：恢复结果应用失败，跟随预测继续运行"
                )
                self._schedule_live_follow_recovery_retry("worker_apply_failed")
            else:
                self._clear_dual_recovery_contexts()
                self.start_dual_motion_button.setEnabled(self._snapshot is not None)
                self.dual_motion_status_label.setText(f"双人实时：恢复结果应用失败 | {exc}")

    def _on_dual_first_frame_worker_failed(self, generation: int, error: Exception) -> None:
        if self._closing or generation != self._dual_first_frame_generation:
            return
        # A one-shot worker may finish cleanup after its accepted result has
        # already been handed to the page.  Such a late failure is a cleanup
        # diagnostic, not a new registration failure; never clear recovery
        # context or overwrite the accepted state in that case.
        if self._dual_first_frame_worker is None:
            self._logger.warning(
                "step=dual_first_frame.worker_failed_ignored generation=%s "
                "reason=terminal_result_already_consumed error=%s",
                generation, error,
            )
            return
        preserve_follow = bool(self._follow_recovery_pending)
        self._dual_first_frame_pending_recovery = False
        worker = self._dual_first_frame_worker
        self._dual_first_frame_worker = None
        if worker is not None and worker not in self._retired_dual_first_frame_workers:
            self._retired_dual_first_frame_workers.append(worker)
        self._logger.error(
            "step=dual_first_frame.worker_failed generation=%s error=%s", generation, error,
        )
        if not preserve_follow:
            self._clear_dual_recovery_contexts()
        elapsed_ms = (
            (time.perf_counter() - self._dual_first_frame_started_at) * 1000.0
            if self._dual_first_frame_started_at is not None else -1.0
        )
        self._dual_first_frame_started_at = None
        if preserve_follow:
            self.dual_motion_status_label.setText(
                "双人实时：后台恢复失败，跟随预测继续运行"
            )
            self._logger.warning(
                "step=dual_motion.recovery_deferred reason=first_frame_worker_failed "
                "follow_prediction_continues=True error=%s",
                error,
            )
            self.stop_dual_motion_button.setEnabled(True)
            self._schedule_live_follow_recovery_retry("first_frame_worker_failed")
        else:
            self.dual_motion_status_label.setText(f"双人实时：后台恢复失败 | {error}")
            self.start_dual_motion_button.setEnabled(self._snapshot is not None)
        self._logger.error(
            "step=dual_first_frame.worker_failed_timing generation=%s elapsed_ms=%.1f",
            generation, elapsed_ms,
        )

    def _on_dual_first_frame_worker_finished(self, generation: int) -> None:
        self._retired_dual_first_frame_workers = [
            worker for worker in self._retired_dual_first_frame_workers
            if worker.generation != generation
        ]
        self._logger.info("step=dual_first_frame.worker_finished generation=%s", generation)

    def _start_dual_motion(
        self, *, recovery: bool, first_frame_ready: bool = False,
        preserve_follow: bool = False,
    ) -> None:
        if self._closing:
            self._logger.info(
                "step=dual_motion.start_ignored reason=page_closing recovery=%s",
                recovery,
            )
            return
        if self._snapshot is None:
            self._show_error(RuntimeError("请先获取当前地图"))
            return
        if not first_frame_ready:
            if self._dual_first_frame_worker is not None and self._dual_first_frame_worker.is_running:
                self.dual_motion_status_label.setText("双人实时：后台首帧恢复仍在进行")
                return
            if any(
                worker.is_running
                for worker in self._retired_dual_first_frame_workers
            ):
                self.dual_motion_status_label.setText("双人实时：等待后台首帧恢复线程退出")
                return
        self.stop_dual_motion(
            clear_first_frame=False,
            preserve_program_probe_recovery=recovery,
            preserve_follow=preserve_follow,
        )
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self.stop_preview()
        if self.capture_monitor_window is not None:
            stop_monitoring = getattr(self.capture_monitor_window, "stop_monitoring", None)
            if callable(stop_monitoring):
                stop_monitoring()
        retired_running = tuple(
            worker
            for worker in self._retired_dual_motion_workers
            if self._dual_worker_is_running(worker)
        )
        if retired_running:
            # A native capture call may ignore stop() until its current frame
            # returns.  Never read a new first frame or create a second worker
            # against the same provider while one of those workers is alive.
            self._dual_motion_restart_pending = bool(recovery)
            self._logger.warning(
                "step=dual_motion.restart_deferred reason=retired_worker_running "
                "recovery=%s retired=%s",
                recovery,
                len(retired_running),
            )
            self.dual_motion_status_label.setText("双人实时：等待旧截图线程退出后恢复")
            return
        if (
            recovery
            and not first_frame_ready
            and hasattr(self.monitor_config, "localization_fps")
        ):
            if self._start_dual_first_frame_async(recovery=True):
                return
            self._logger.error(
                "step=program_probe.relocalization_failed "
                "reason=background_first_frame_unavailable"
            )
            if not preserve_follow:
                self._clear_dual_recovery_contexts()
                self.dual_motion_status_label.setText("双人实时：无法启动后台恢复定位")
            else:
                self._logger.warning(
                    "step=dual_motion.recovery_deferred reason=background_first_frame_unavailable "
                    "follow_prediction_continues=True",
                )
            return
        # A recovery must take a fresh memory anchor and a fresh visual frame.
        # Reusing the old registration would preserve the transform that just
        # lost contact with the live character. Normal starts still reuse a
        # successful manual first-frame run to avoid transient-frame failures.
        # ``first_frame_ready`` is the hand-off from the asynchronous recovery
        # worker.  The worker has already applied its bundle to
        # ``_last_dual_first_frame_result`` and ``_dual_initial_frame``; do not
        # clear the result merely because this restart is a recovery.  The old
        # expression (``None if recovery else ...``) made an accepted worker
        # result fail the validation below when ``first_frame_ready=True``.
        result = self._last_dual_first_frame_result
        self._logger.info(
            "step=dual_motion.first_frame_context recovery=%s first_frame_ready=%s "
            "status=%s accepted=%s has_frame=%s",
            recovery,
            first_frame_ready,
            None if result is None else result.status,
            None if result is None else result.accepted,
            self._dual_initial_frame is not None,
        )
        if (
            not first_frame_ready
            and (recovery or result is None or not result.accepted or self._dual_initial_frame is None)
        ):
            if recovery:
                self._logger.info(
                    "step=program_probe.relocalization_started recovery=%s "
                    "attempt=%s target=%s role=%s",
                    recovery,
                    self._program_probe_recovery_attempts,
                    self._program_probe_recovery_target,
                    self._program_probe_recovery_identity,
                )
            self.run_dual_first_frame_experiment(
                render_map=False,
                force_memory_read=recovery,
            )
            result = self._last_dual_first_frame_result
        if result is None or not result.accepted or self._dual_initial_frame is None:
            self.dual_motion_status_label.setText("双人实时：首帧配准未通过")
            if recovery:
                self._logger.error(
                    "step=program_probe.relocalization_failed reason=first_frame_rejected"
                )
                if not preserve_follow:
                    self._clear_dual_recovery_contexts()
                else:
                    self._logger.warning(
                        "step=dual_motion.recovery_deferred reason=first_frame_rejected "
                        "follow_prediction_continues=True",
                    )
            return
        try:
            reference = self._map_orientation().transform_reference(build_reference(self._snapshot))
            if self.dual_motion_tracker_factory is not None:
                tracker = self.dual_motion_tracker_factory(reference)
            else:
                runtime = MapRuntime.from_wall_layer(
                    reference_boundary_layer(reference),
                    map_id=self._snapshot.metadata.area_id,
                    map_version=self._snapshot.metadata.instance_id,
                )
                tracker = DualVisualTracker(
                    LocalMapMatcher(runtime, max_error=4.0, min_margin=0.02),
                    marker_hold_ms=round(self.dual_marker_hold_seconds.value() * 1000),
                    marker_max_uncertainty=self.dual_marker_error_limit.value(),
                )
            initial = tracker.start(self._dual_initial_frame, result, self._dual_initial_candidates)
            base = terrain_pixmap(self._snapshot, self._map_orientation())
            self.map_widget.set_image(prepare_localization_map(base, initial.transform))
            self._dual_map_source_size = (base.width(), base.height())
            self._dual_motion_tracker = tracker
            self._dual_motion_frame_count = 0
            self._dual_evidence_count = 0
            self._dual_evidence_signature = None
            self._dual_map_transform = initial.transform
            self._dual_follow_reference = reference
            self._latest_dual_state = initial
            self._render_dual_motion_state(initial, self._dual_map_source_size)
            self.start_follow_button.setEnabled(True)
            self.start_dual_target_button.setEnabled(True)
            # Production monitor profiles expose localization_fps and use the
            # bounded worker.  Minimal test/dummy configs intentionally keep
            # the legacy synchronous hook so existing deterministic page tests
            # can call _tick_dual_motion() directly.
            worker = None
            if hasattr(self.monitor_config, "localization_fps"):
                self._dual_motion_generation += 1
                worker_recognizer = None
                # HSVRecognizer owns a CLAHE native object.  Keep the GUI
                # recognizer out of the capture thread even though the
                # current page normally stops preview before starting this
                # loop; this also makes reopening the monitor window safe.
                try:
                    get_params = getattr(self.recognizer, "get_params", None)
                    set_params = getattr(self.recognizer, "set_params", None)
                    if callable(get_params) and callable(set_params):
                        candidate = type(self.recognizer)()
                        candidate.set_params(dict(get_params()))
                        worker_recognizer = candidate
                except Exception:
                    self._logger.exception(
                        "step=dual_motion.worker_recognizer_clone_failed; falling back to synchronous capture"
                    )
                if worker_recognizer is not None:
                    worker = Poe2DualMotionWorker(
                        tracker=tracker,
                        preview_provider=self.preview_provider,
                        recognizer=worker_recognizer,
                        monitor_config=self.monitor_config,
                        fps=int(getattr(self.monitor_config, "localization_fps", 30)),
                        generation=self._dual_motion_generation,
                        cleanup=getattr(self.preview_provider, "close_current_thread", None),
                    )
                    worker.result_available.connect(self._on_dual_worker_result)
                    worker.frame_failed.connect(self._on_dual_worker_frame_failed)
                    worker.failed.connect(self._on_dual_worker_failed)
                    worker.finished.connect(self._on_dual_worker_finished)
                    self._dual_motion_worker = worker
                    # This timer only drains the latest completed result; capture
                    # and recognition no longer run in the Qt GUI thread.
                    # The worker is configured for 30 FPS.  A 16 ms drain
                    # wakes Qt twice for most completed frames without
                    # producing another capture result; 33 ms matches the
                    # producer cadence and keeps the UI responsive when
                    # preview/overlay work is active.
                    self._dual_motion_timer.setInterval(self._DUAL_WORKER_DRAIN_INTERVAL_MS)
                else:
                    self._logger.warning(
                        "step=dual_motion.worker_disabled reason=recognizer_not_isolated "
                        "fallback=synchronous_capture"
                    )
                    self._dual_motion_timer.setInterval(self._localization_interval())
            else:
                self._dual_motion_timer.setInterval(self._localization_interval())
            self._dual_motion_timer.start()
            if worker is not None:
                worker.start()
            self.start_dual_motion_button.setEnabled(False)
            self.stop_dual_motion_button.setEnabled(True)
            self._logger.info(
                "step=dual_motion.started instance=%s interval_ms=%s memory_reads=%s recovery=%s",
                self._snapshot.metadata.instance_id,
                self._dual_motion_timer.interval(),
                self._dual_first_frame_read_count,
                recovery,
            )
            if recovery:
                self._logger.info(
                    "step=program_probe.relocalization_registration_success "
                    "memory_reads=%s transform=%s; waiting_for_fresh_visual_frame=True",
                    self._dual_first_frame_read_count,
                    getattr(initial, "transform", None),
                )
        except Exception as exc:
            # Keep an accepted manual first frame available for a retry.  A
            # failed realtime construction must not force a new memory read
            # and transient screenshot registration.
            self.stop_dual_motion(
                clear_first_frame=False,
                preserve_follow=bool(preserve_follow),
            )
            self._logger.exception("step=dual_motion.start_failed")
            self.dual_motion_status_label.setText(f"双人实时：启动失败 | {exc}")
            self._show_error(exc)
            if recovery:
                self._logger.error(
                    "step=program_probe.relocalization_failed reason=tracker_start_failed error=%s",
                    exc,
                )
                if not preserve_follow:
                    self._clear_dual_recovery_contexts()
                else:
                    self._follow_recovery_pending = True
                    self._schedule_live_follow_recovery_retry("tracker_start_failed")

    def stop_dual_motion(
        self,
        *,
        clear_first_frame: bool = True,
        preserve_program_probe_recovery: bool = False,
        preserve_follow: bool = False,
    ) -> None:
        # A user-initiated stop, a worker failure, and a map reset all cancel
        # any delayed restart request.  The recovery path sets a new pending
        # value only after this method returns, so this cannot cancel a fresh
        # request that is currently being scheduled.
        self._dual_motion_restart_pending = None
        self.stop_program_move_probe(
            _preserve_recovery=preserve_program_probe_recovery,
        )
        if not preserve_follow:
            self.stop_follow_experiment(
                _preserve_recovery=preserve_program_probe_recovery,
            )
        else:
            self._logger.info(
                "step=follow_experiment.recovery_transition "
                "action=preserve_session output_kept=True timer_kept=True",
            )
        self.stop_dual_target_experiment(
            _preserve_recovery=preserve_program_probe_recovery,
        )
        was_active = self._dual_motion_timer.isActive()
        self._dual_motion_timer.stop()
        first_frame_worker = self._dual_first_frame_worker
        if first_frame_worker is not None:
            first_frame_worker.stop()
            wait = getattr(first_frame_worker, "wait", None)
            stopped = wait(0) if callable(wait) else True
            self._dual_first_frame_worker = None
            self._dual_first_frame_pending_recovery = False
            self._dual_first_frame_started_at = None
            if not stopped:
                self._logger.info(
                    "step=dual_first_frame.worker_retired generation=%s",
                    first_frame_worker.generation,
                )
            if first_frame_worker not in self._retired_dual_first_frame_workers:
                self._retired_dual_first_frame_workers.append(first_frame_worker)
        worker = self._dual_motion_worker
        if worker is not None:
            worker.stop()
            wait = getattr(worker, "wait", None)
            # Do not hold the Qt event loop for a native capture call.  The
            # worker remains strongly referenced in the retired list and its
            # finished signal schedules any deferred recovery restart after
            # the capture backend has actually returned.
            stopped = wait(0) if callable(wait) else True
            # Keep the QObject strongly referenced until its queued
            # ``finished`` signal has been delivered, even when the Python
            # thread joined successfully.  Dropping it immediately can let
            # Qt tear down a signal/slot connection while a native preview
            # frame is still being retired, which is a known Qt6Gui crash
            # boundary on Windows.
            self._dual_motion_worker = None
            if worker not in self._retired_dual_motion_workers:
                self._retired_dual_motion_workers.append(worker)
            if stopped:
                self._logger.info(
                    "step=dual_motion.worker_stop_completed generation=%s",
                    self._dual_motion_generation,
                )
            else:
                # Do not destroy the last Python reference while native
                # capture is still running.  Keep it until its finished
                # signal arrives so a late callback cannot use freed state.
                self._logger.warning(
                    "step=dual_motion.worker_stop_deferred generation=%s retired=%s "
                    "reason=native_capture_still_returning",
                    self._dual_motion_generation,
                    len(self._retired_dual_motion_workers),
                )
        self._dual_motion_tracker = None
        if not preserve_follow:
            self._dual_map_source_size = None
            self._dual_map_transform = None
            self._dual_follow_reference = None
            self._latest_dual_state = None
            self._latest_dual_captured_at_ms = None
            self._latest_dual_processed = None
        if clear_first_frame:
            self._last_dual_first_frame_result = None
            self._dual_initial_frame = None
            self._dual_initial_candidates = ()
        if not preserve_follow:
            self.start_follow_button.setEnabled(False)
        self.start_dual_target_button.setEnabled(False)
        self.start_dual_motion_button.setEnabled(self._snapshot is not None)
        if not preserve_follow:
            self.stop_dual_motion_button.setEnabled(False)
        if was_active:
            if preserve_follow:
                self.dual_motion_status_label.setText("双人实时：视觉恢复中，跟随预测继续")
                self._logger.info(
                    "step=dual_motion.recovery_transition frames=%s "
                    "follow_prediction_continues=True",
                    self._dual_motion_frame_count,
                )
            else:
                self.dual_motion_status_label.setText("双人实时：已停止")
                self._logger.info("step=dual_motion.stopped frames=%s", self._dual_motion_frame_count)

    def _on_dual_worker_result(self, generation: int) -> None:
        if self._closing or generation != self._dual_motion_generation:
            return
        try:
            self._drain_dual_motion_worker()
        except Exception as exc:
            self._logger.exception("step=dual_motion.result_dispatch_failed error=%s", exc)
            continued = self._continue_live_follow_after_dual_failure(
                "result_dispatch_failed", exc,
            )
            if not continued:
                self.stop_dual_motion()
                self.dual_motion_status_label.setText(f"双人实时：渲染失败 | {exc}")

    def _on_dual_worker_failed(self, generation: int, error: Exception) -> None:
        if self._closing or generation != self._dual_motion_generation:
            return
        self._logger.error("step=dual_motion.worker_failed error=%s", error)
        continued = self._continue_live_follow_after_dual_failure("worker_failed", error)
        if not continued:
            self.stop_dual_motion()
            self.dual_motion_status_label.setText(f"双人实时：失败 | {error}")
            self._show_error(error)

    def _on_dual_worker_frame_failed(
        self, generation: int, error: Exception, consecutive_failures: int
    ) -> None:
        if self._closing or generation != self._dual_motion_generation:
            return
        worker = self._dual_motion_worker
        max_failures = int(getattr(worker, "max_consecutive_failures", 3) or 3)
        if (
            consecutive_failures > 1
            and consecutive_failures < max_failures
            and consecutive_failures % 5 != 0
        ):
            self._dual_frame_failure_suppressed += 1
            return
        suppressed = self._dual_frame_failure_suppressed
        self._dual_frame_failure_suppressed = 0
        self._logger.warning(
            "step=dual_motion.frame_failed generation=%s consecutive=%s "
            "failed_frames=%s suppressed=%s error=%s",
            generation,
            consecutive_failures,
            getattr(worker, "failed_frames", None),
            suppressed,
            error,
        )

    def _on_dual_worker_finished(self, generation: int) -> None:
        self._logger.info("step=dual_motion.worker_finished generation=%s", generation)
        self._retired_dual_motion_workers = [
            worker
            for worker in self._retired_dual_motion_workers
            if worker.generation != generation
        ]
        pending = self._dual_motion_restart_pending
        if self._closing or self._snapshot is None:
            self._dual_motion_restart_pending = None
            if pending is not None:
                self._logger.info(
                    "step=dual_motion.restart_cancelled reason=page_not_active "
                    "closing=%s has_snapshot=%s",
                    self._closing,
                    self._snapshot is not None,
                )
            return
        if (
            pending is not None
            and self._dual_motion_worker is None
            and not any(
                self._dual_worker_is_running(worker)
                for worker in self._retired_dual_motion_workers
            )
        ):
            self._dual_motion_restart_pending = None
            session_token = self._dual_motion_session_token
            self._logger.info(
                "step=dual_motion.restart_resumed generation=%s recovery=%s",
                generation,
                pending,
            )
            QTimer.singleShot(
                0,
                lambda recovery=pending, token=session_token: self._resume_dual_motion_restart(
                    recovery=recovery,
                    session_token=token,
                ),
            )

    def _begin_live_follow_recovery_episode(self, reason: str) -> None:
        """Open one recovery episode for the active live-follow session."""
        if self._follow_recovery_episode_active:
            return
        self._recovery_controller.observe(
            RecoveryObservation(str(reason), recovery_requested=True)
        )
        self._follow_recovery_episode_active = True
        self._follow_recovery_episode_reason = str(reason)
        self._follow_recovery_episode_suppressed = 0
        self._logger.info(
            "step=live_role_follow.recovery_episode_started reason=%s session_id=%s",
            reason,
            self._follow_session_id,
        )

    def _clear_live_follow_recovery_episode(self, reason: str) -> None:
        """Close the episode after a fresh/stable observation is accepted."""
        if self._follow_recovery_episode_active:
            self._logger.info(
                "step=live_role_follow.recovery_episode_cleared reason=%s "
                "episode_reason=%s suppressed=%s session_id=%s",
                reason,
                self._follow_recovery_episode_reason,
                self._follow_recovery_episode_suppressed,
                self._follow_session_id,
            )
        self._follow_recovery_episode_active = False
        self._follow_recovery_episode_reason = None
        self._follow_recovery_episode_suppressed = 0
        self._recovery_controller.clear(reason)
        self._follow_recovery_retry_delay_ms = 0

    def _continue_live_follow_after_dual_failure(
        self, reason: str, error: Exception | None = None,
    ) -> bool:
        """Keep an active live-follow session alive across capture failures.

        Visual/capture failures are recoverable observations. They may release
        the current stick output, but they must not destroy the follow runtime,
        timer, target session, or prediction state. The recovery retry rebuilds
        the visual worker and re-anchors when a fresh frame arrives.
        """
        active = bool(self._follow_live_mode and self._follow_runtime is not None)
        if not active:
            return False
        if self._follow_recovery_episode_active:
            self._follow_recovery_episode_suppressed += 1
            if self._follow_recovery_episode_suppressed == 1 or (
                self._follow_recovery_episode_suppressed % 25 == 0
            ):
                self._logger.info(
                    "step=live_role_follow.recovery_episode_suppressed reason=%s "
                    "source=dual_failure count=%s episode_reason=%s",
                    reason,
                    self._follow_recovery_episode_suppressed,
                    self._follow_recovery_episode_reason,
                )
            self._follow_recovery_pending = True
            self._schedule_live_follow_recovery_retry("episode_suppressed")
            return True
        self._begin_live_follow_recovery_episode(reason)
        self._follow_recovery_pending = True
        if self._follow_program_output is not None:
            try:
                self._follow_program_output.release_all()
            except Exception:
                self._logger.exception(
                    "step=live_role_follow.recovery_release_failed reason=%s", reason,
                )
        self._logger.warning(
            "step=live_role_follow.recovery_deferred reason=%s "
            "follow_prediction_continues=True error=%s",
            reason, error,
        )
        self.dual_motion_status_label.setText("双人实时：视觉链路暂时异常，跟随预测继续")
        self.follow_status_label.setText("实时跟随：视觉链路暂时异常，跟随预测继续")
        self.stop_dual_motion(
            preserve_program_probe_recovery=True,
            preserve_follow=True,
        )
        self._schedule_live_follow_recovery_retry(reason)
        return True

    @staticmethod
    def _dual_worker_is_running(worker: Any) -> bool:
        value = getattr(worker, "is_running", False)
        return bool(value() if callable(value) else value)

    def _resume_dual_motion_restart(self, *, recovery: bool, session_token: int) -> None:
        if (
            self._closing
            or session_token != self._dual_motion_session_token
            or self._snapshot is None
        ):
            self._logger.info(
                "step=dual_motion.restart_cancelled reason=session_changed "
                "closing=%s token=%s current_token=%s has_snapshot=%s",
                self._closing,
                session_token,
                self._dual_motion_session_token,
                self._snapshot is not None,
            )
            return
        # A retired capture worker can finish after an active live-follow
        # session requested recovery. Preserve that session when the fresh
        # worker is finally allowed to start.
        preserve_follow = bool(self._follow_live_mode and self._follow_runtime is not None)
        self._start_dual_motion(
            recovery=recovery,
            preserve_follow=preserve_follow,
        )

    def _drain_dual_motion_worker(self) -> None:
        worker = self._dual_motion_worker
        if worker is None:
            return
        result = worker.take_latest()
        if result is None:
            return
        if self._follow_live_mode and self._follow_runtime is not None:
            foreground, foreground_reason = self._refresh_follow_game_window()
            if not foreground:
                # Do not let a browser/Workbench frame become the latest
                # localization state.  The normal follow tick will hold the
                # output at the foreground gate and wait for a real PoE2
                # frame, instead of counting this frame as marker loss.
                self._logger.warning(
                    "step=dual_motion.capture_frame_ignored reason=%s "
                    "captured_at_ms=%s pid=%s hwnd=%s",
                    foreground_reason,
                    result.captured_at_ms,
                    self._follow_game_pid,
                    self._follow_game_hwnd,
                )
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                return
        state = result.state
        self._dual_motion_frame_count += 1
        self._latest_dual_state = state
        self._latest_dual_captured_at_ms = int(result.captured_at_ms)
        self._latest_dual_raw = result.raw
        self._latest_dual_combined = result.combined
        self._latest_dual_processed = getattr(result, "processed", None)
        self._record_dual_observation_evidence(
            state, result.raw, result.candidates, result.captured_at_ms,
        )
        now = time.perf_counter()
        if now - self._dual_last_ui_render_at >= 1.0 / 12.0:
            self._dual_last_ui_render_at = now
            self._render_preview(
                result.raw,
                combined=result.combined,
                processed=getattr(result, "processed", None),
            )
        source_size = self._dual_map_source_size
        if source_size is not None:
            self._render_dual_motion_state(state, source_size)
        if self._dual_motion_frame_count % 30 == 0 or state.status != "tracking":
            self._logger.info(
                "step=dual_motion.tick frame=%s status=%s reason=%s quality=%.3f "
                "visible=%s correction=%s recovery=%s diagnostics=%s",
                self._dual_motion_frame_count, state.status, state.reason,
                state.wall_quality, tuple(k for k, v in state.players.items() if v is not None),
                state.correction_attempted, state.recovery_requested, dict(state.diagnostics),
            )
            self._logger.info(
                "step=dual_motion.timing frame=%s capture_ms=%.1f recognition_ms=%.1f "
                "tracking_ms=%.1f total_worker_ms=%.1f dropped_results=%s completed_frames=%s",
                self._dual_motion_frame_count,
                result.capture_ms,
                result.recognition_ms,
                result.tracking_ms,
                result.capture_ms + result.recognition_ms + result.tracking_ms,
                worker.dropped_results,
                worker.completed_frames,
            )
        revision = worker.take_pending_recovery_revision()
        if revision or state.recovery_requested:
            revision = revision or state.recovery_revision
            self._logger.warning("step=dual_motion.recovery revision=%s", revision)
            live_follow_recovery = bool(
                self._follow_live_mode and self._follow_runtime is not None
            )
            recovery_episode_already_active = bool(
                live_follow_recovery and self._follow_recovery_episode_active
            )
            if recovery_episode_already_active:
                self._follow_recovery_episode_suppressed += 1
                self._follow_recovery_pending = True
                if self._follow_recovery_episode_suppressed == 1 or (
                    self._follow_recovery_episode_suppressed % 25 == 0
                ):
                    self._logger.info(
                        "step=live_role_follow.recovery_episode_suppressed "
                        "reason=%s source=dual_motion count=%s",
                        state.reason, self._follow_recovery_episode_suppressed,
                    )
                return
            if live_follow_recovery:
                self._begin_live_follow_recovery_episode(f"motion:{state.reason}")
            if not self._claim_dual_recovery(reason=f"motion:{state.reason}"):
                if live_follow_recovery:
                    self._follow_recovery_pending = True
                    self.dual_motion_status_label.setText(
                        "双人实时：视觉恢复冷却中，跟随预测继续"
                    )
                    self._logger.warning(
                        "step=dual_motion.recovery_deferred reason=cooldown "
                        "follow_prediction_continues=True revision=%s",
                        revision,
                    )
                    return
                self.stop_dual_motion()
                self.dual_motion_status_label.setText("双人实时：恢复后连续失配，请检查监控配置并手动重启")
                self._logger.warning("step=dual_motion.recovery_cooldown revision=%s", revision)
                return
            self._save_dual_follow_recovery_context()
            self._save_dual_target_recovery_context()
            self._follow_recovery_pending = live_follow_recovery
            self.stop_dual_motion(
                preserve_program_probe_recovery=True,
                preserve_follow=live_follow_recovery,
            )
            if live_follow_recovery:
                self._start_dual_motion(recovery=True, preserve_follow=True)
            else:
                self._start_dual_motion(recovery=True)
            return
        self._maybe_resume_program_probe_after_relocalization()
        self._maybe_resume_dual_follow_after_relocalization()
        self._maybe_resume_dual_target_after_relocalization()

    def _tick_dual_motion(self) -> None:
        if self._dual_motion_worker is not None:
            self._drain_dual_motion_worker()
            return
        source_size = self._dual_map_source_size
        if (
            self._dual_motion_tracker is None
            or self.preview_provider is None
            or self.recognizer is None
            or source_size is None
        ):
            return
        tick_started = time.perf_counter()
        try:
            raw = self.preview_provider(self.monitor_config)
            if raw is None:
                raise RuntimeError("截图后端返回空帧")
            if self._follow_live_mode and self._follow_runtime is not None:
                foreground, foreground_reason = self._refresh_follow_game_window()
                if not foreground:
                    self._logger.warning(
                        "step=dual_motion.capture_frame_ignored reason=%s "
                        "pid=%s hwnd=%s",
                        foreground_reason,
                        self._follow_game_pid,
                        self._follow_game_hwnd,
                    )
                    if self._follow_program_output is not None:
                        self._follow_program_output.release_all()
                    return
            capture_elapsed_ms = (time.perf_counter() - tick_started) * 1000.0
            captured_at_ms = int(time.time() * 1000)
            # Reuse the wall preprocessing result for the preview instead of
            # running the expensive preprocessing a second time every few
            # frames.  The fallback keeps compatibility with test/dummy
            # recognizers that only expose ``extract_combined``.
            processed = None
            extract_with_processed = getattr(self.recognizer, "extract_combined_with_processed", None)
            if callable(extract_with_processed):
                processed, combined = extract_with_processed(
                    raw, player_pos=None, exclude_player=False, exclude_dynamic=False,
                )
            else:
                combined = self.recognizer.extract_combined(
                    raw, player_pos=None, exclude_player=False, exclude_dynamic=False,
                )
            recognition_elapsed_ms = (time.perf_counter() - tick_started) * 1000.0 - capture_elapsed_ms
            mask = combined[0] if isinstance(combined, (tuple, list)) else combined
            profiles = tuple(
                MarkerColorProfile.from_dict(item)
                for item in getattr(self.monitor_config, "dual_marker_profiles", ())
            )
            observation = detect_saturated_marker_observation(
                raw, captured_at_ms, profiles=profiles or None,
            )
            frame = HybridFrame(
                captured_at_ms, captured_at_ms, mask,
                (float(mask.shape[1]) / 2.0, float(mask.shape[0]) / 2.0),
            )
            candidates = marker_candidates_from_observation(observation, max_candidates=6)
            hints = {
                identity: RolePredictionHint((value[0], value[1]), value[2], value[3])
                for identity, value in self._current_follow_prediction_hints(captured_at_ms).items()
            }
            state = (
                self._dual_motion_tracker.tick(frame, candidates, prediction_hints=hints)
                if hints else self._dual_motion_tracker.tick(frame, candidates)
            )
            tracking_elapsed_ms = (time.perf_counter() - tick_started) * 1000.0 - capture_elapsed_ms - recognition_elapsed_ms
            self._dual_motion_frame_count += 1
            self._latest_dual_state = state
            self._latest_dual_captured_at_ms = captured_at_ms
            self._latest_dual_raw = raw
            self._latest_dual_combined = combined
            self._latest_dual_processed = processed
            self._record_dual_observation_evidence(state, raw, candidates, captured_at_ms)
            if self._dual_motion_frame_count % 3 == 0:
                self._render_preview(raw, combined=combined, processed=processed)
            self._render_dual_motion_state(state, source_size)
            self._maybe_resume_program_probe_after_relocalization()
            self._maybe_resume_dual_follow_after_relocalization()
            self._maybe_resume_dual_target_after_relocalization()
            if self._dual_motion_frame_count % 30 == 0 or state.status != "tracking":
                self._logger.info(
                    "step=dual_motion.tick frame=%s status=%s reason=%s quality=%.3f "
                    "visible=%s correction=%s recovery=%s diagnostics=%s",
                    self._dual_motion_frame_count, state.status, state.reason,
                    state.wall_quality, tuple(k for k, v in state.players.items() if v is not None),
                    state.correction_attempted, state.recovery_requested, dict(state.diagnostics),
                )
                self._logger.info(
                    "step=dual_motion.timing frame=%s capture_ms=%.1f recognition_ms=%.1f tracking_ms=%.1f total_ms=%.1f",
                    self._dual_motion_frame_count,
                    capture_elapsed_ms,
                    recognition_elapsed_ms,
                    tracking_elapsed_ms,
                    (time.perf_counter() - tick_started) * 1000.0,
                )
            if state.recovery_requested:
                self._logger.warning("step=dual_motion.recovery revision=%s", state.recovery_revision)
                live_follow_recovery = bool(
                    self._follow_live_mode and self._follow_runtime is not None
                )
                recovery_episode_already_active = bool(
                    live_follow_recovery and self._follow_recovery_episode_active
                )
                if recovery_episode_already_active:
                    self._follow_recovery_episode_suppressed += 1
                    self._follow_recovery_pending = True
                    if self._follow_recovery_episode_suppressed == 1 or (
                        self._follow_recovery_episode_suppressed % 25 == 0
                    ):
                        self._logger.info(
                            "step=live_role_follow.recovery_episode_suppressed "
                            "reason=%s source=dual_motion count=%s",
                            state.reason, self._follow_recovery_episode_suppressed,
                        )
                    return
                if live_follow_recovery:
                    self._begin_live_follow_recovery_episode(f"motion:{state.reason}")
                if not self._claim_dual_recovery(reason=f"motion:{state.reason}"):
                    if live_follow_recovery:
                        self._follow_recovery_pending = True
                        self.dual_motion_status_label.setText(
                            "双人实时：视觉恢复冷却中，跟随预测继续"
                        )
                        self._logger.warning(
                            "step=dual_motion.recovery_deferred reason=cooldown "
                            "follow_prediction_continues=True revision=%s",
                            state.recovery_revision,
                        )
                        return
                    self.stop_dual_motion()
                    self.dual_motion_status_label.setText(
                        "双人实时：恢复后连续失配，请检查监控配置并手动重启"
                    )
                    self._logger.warning(
                        "step=dual_motion.recovery_cooldown revision=%s",
                        state.recovery_revision,
                    )
                    return
                self._save_dual_follow_recovery_context()
                self._save_dual_target_recovery_context()
                self._follow_recovery_pending = live_follow_recovery
                self.stop_dual_motion(
                    preserve_program_probe_recovery=True,
                    preserve_follow=live_follow_recovery,
                )
                if live_follow_recovery:
                    self._start_dual_motion(recovery=True, preserve_follow=True)
                else:
                    self._start_dual_motion(recovery=True)
        except Exception as exc:
            self._logger.exception("step=dual_motion.tick_failed")
            continued = self._continue_live_follow_after_dual_failure("tick_failed", exc)
            if not continued:
                self.stop_dual_motion()
                self.dual_motion_status_label.setText(f"双人实时：失败 | {exc}")

    def _record_dual_observation_evidence(
        self, state: Any, raw: Any, candidates: Any, captured_at_ms: int,
    ) -> None:
        if state.status == "tracking":
            self._dual_evidence_signature = None
            return
        if raw is None or self._dual_evidence_count >= 6:
            return
        diagnostics = dict(getattr(state, "diagnostics", {}) or {})
        signature = (
            state.status, state.reason,
            tuple(diagnostics.get("missing_identities", ())),
            tuple(diagnostics.get("expired_marker_identities", ())),
        )
        if signature == self._dual_evidence_signature:
            return
        root = getattr(self.archive, "root", None)
        if root is None:
            return
        try:
            profiles = tuple(
                MarkerColorProfile.from_dict(item)
                for item in getattr(self.monitor_config, "dual_marker_profiles", ())
            )
            path = save_dual_occlusion_evidence(
                root, raw=raw, profiles=profiles, candidates=tuple(candidates),
                frame_id=int(diagnostics.get("failed_frame_id", captured_at_ms)),
                captured_at_ms=int(captured_at_ms), status=state.status,
                reason=state.reason, diagnostics=diagnostics,
            )
        except Exception as exc:
            self._logger.warning("step=dual_motion.evidence_failed error=%s", exc)
            return
        self._dual_evidence_count += 1
        self._dual_evidence_signature = signature
        self._logger.info(
            "step=dual_motion.evidence_saved path=%s count=%s",
            path, self._dual_evidence_count,
        )

    def _render_dual_motion_state(self, state: Any, source_size: tuple[int, int]) -> None:
        self._latest_dual_state = state
        self._sync_follow_role_choices(state.players)
        visible = {
            identity: localization_display_point(
                point, source_size=source_size, transform=state.transform,
            )
            for identity, point in state.players.items() if point is not None
        }
        identities = tuple(state.players)
        primary = visible.get(identities[0]) if identities else None
        secondary = tuple(visible[identity] for identity in identities[1:] if identity in visible)
        if self._follow_runtime is not None:
            # The visual tracker and the follow timer share one map widget;
            # render the follow overlay once.  Do not first paint the plain
            # tracker overlay and then immediately replace it: that causes
            # duplicate Qt updates and briefly hides the predicted route.
            self._render_follow_overlay()
        elif self._dual_target_runtime is not None:
            self._render_dual_target_overlay()
        else:
            self.map_widget.set_overlay(
                position=primary,
                candidates=secondary,
                target=self._clicked_target_display,
            )
        focus = primary or (secondary[0] if secondary else None)
        if focus is not None:
            self.map_widget.focus_on_point(focus, zoom_multiplier=self.map_follow_zoom_multiplier)
        positions = " | ".join(
            f"{identity}: {point[0]:.1f},{point[1]:.1f}" if point is not None else f"{identity}: 未识别"
            for identity, point in state.players.items()
        )
        self.dual_motion_status_label.setText(
            f"双人实时：{state.status} | {state.reason} | {positions} | 墙体 {state.wall_quality:.2f}"
        )

    def _sync_follow_role_choices(self, players: Any) -> None:
        identities = tuple(str(identity) for identity in players)
        for combo, prompt in (
            (self.follow_p1_combo, "选择 P1 角色"),
            (self.follow_p2_combo, "选择 P2 角色"),
            (self.dual_target_p1_combo, "选择 P1 角色"),
            (self.dual_target_p2_combo, "选择 P2 角色"),
        ):
            existing = tuple(combo.itemData(index) for index in range(1, combo.count()))
            if existing == identities:
                continue
            selected = combo.currentData()
            combo.clear()
            combo.addItem(prompt, None)
            for identity in identities:
                combo.addItem(identity, identity)
            if selected in identities:
                combo.setCurrentIndex(combo.findData(selected))
        if hasattr(self, "program_probe_role_combo"):
            selected = self.program_probe_role_combo.currentData()
            self.program_probe_role_combo.clear()
            self.program_probe_role_combo.addItem("选择移动角色", None)
            for identity in identities:
                self.program_probe_role_combo.addItem(identity, identity)
            if selected in identities:
                self.program_probe_role_combo.setCurrentIndex(
                    self.program_probe_role_combo.findData(selected)
                )

    def _append_session_log(self, message: str) -> None:
        """Append one formatted logger record without growing the page layout."""
        if hasattr(self, "session_log"):
            self.session_log.appendPlainText(str(message))

    def _sync_follow_radius_control(self) -> None:
        live_mode = self.follow_mode_combo.currentData() in {"p1_leads", "p2_leads"}
        editable = live_mode and self._follow_runtime is None
        self.follow_radius_label.setEnabled(editable)
        self.follow_footprint_radius.setEnabled(editable)

    def stop_all_program_motion(self) -> None:
        """Release every program-controlled experiment without stopping visual tracking."""
        self.stop_program_move_probe(reason="已停止全部程序移动")
        self.stop_follow_experiment()
        self.stop_dual_target_experiment()
        self._logger.info("step=program_motion.stop_all_requested")

    def start_program_move_probe(self) -> None:
        """Arm a standalone map-point movement test; no input is sent yet."""
        self.stop_dual_target_experiment()
        if self._program_probe_timer.isActive() or self._program_probe_waiting_click:
            return
        if self.program_output_factory is None:
            self.program_probe_status_label.setText("程序移动实验：虚拟手柄输出未绑定")
            return
        if self._latest_dual_state is None or self._dual_follow_reference is None:
            self.program_probe_status_label.setText("程序移动实验：请先完成双人首帧和实时定位")
            return
        identity = self.program_probe_role_combo.currentData()
        if not identity:
            self.program_probe_status_label.setText("程序移动实验：请选择要移动的角色")
            return
        self.stop_follow_experiment()
        self._program_probe_waiting_click = True
        # A new user-armed movement experiment starts a fresh recovery budget;
        # an automatic resume keeps the previous timestamp for cooldown.
        self._program_probe_last_relocalization_at_ms = None
        self.program_probe_button.setEnabled(False)
        self.program_probe_stop_button.setEnabled(True)
        self.program_probe_status_label.setText(
            "已准备，不会立即发送输入；请在左侧大地图点击一个目标位置"
        )
        self._logger.info(
            "step=program_probe.armed_waiting_click role=%s controller=%s",
            identity,
            self.program_probe_controller_combo.currentData(),
        )

    def _start_program_move_probe_at(
        self, point: tuple[float, float], *, _confirmed: bool = False
    ) -> None:
        if not self._program_probe_waiting_click and not _confirmed:
            return
        identity = str(self.program_probe_role_combo.currentData() or "")
        state = self._latest_dual_state
        reference = self._dual_follow_reference
        if not identity or state is None or reference is None:
            self._logger.warning(
                "step=program_probe.start_rejected reason=missing_context role=%s "
                "has_state=%s has_reference=%s",
                identity or None,
                state is not None,
                reference is not None,
            )
            self.stop_program_move_probe()
            return
        current = state.players.get(identity)
        if current is None:
            self._logger.warning(
                "step=program_probe.start_rejected reason=missing_player_position role=%s",
                identity,
            )
            self.program_probe_status_label.setText("程序移动实验：所选角色当前没有可信位置")
            return
        if not _confirmed:
            answer = QMessageBox.question(
                self,
                "确认发送真实手柄输入",
                "确认后等待 10 秒切回 PoE2，再持续控制选定角色向地图目标移动；"
                "到达、阻塞、失焦或点击停止时会自动中性并释放。\n"
                "请确认游戏已打开、虚拟手柄已连接，并准备好管理员权限。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._logger.info("step=program_probe.cancelled_by_user")
                self.program_probe_status_label.setText("已取消真实输入确认，仍可重新点击目标")
                return
            self._program_probe_pending_point = point
            self._program_probe_waiting_click = False
            self.program_probe_status_label.setText("已确认，10 秒内切回 PoE2；尚未发送输入")
            self._logger.info("step=program_probe.waiting_game_foreground seconds=10")
            self._program_probe_arm_timer.start(10_000)
            return
        point = self._program_probe_pending_point or point
        self._program_probe_pending_point = None
        try:
            game_pid = int(find_process_id())
            game_window = find_process_window(game_pid, title_substring="Path of Exile 2")
        except Exception as exc:
            self._logger.exception("step=program_probe.window_lookup_failed")
            self.stop_program_move_probe(reason=f"无法获取 PoE2 窗口：{exc}")
            return
        if game_window is None:
            self.stop_program_move_probe(reason="未找到 PoE2 可见窗口，未发送输入")
            return
        if not is_process_foreground(game_pid):
            self.stop_program_move_probe(reason="PoE2 当前不在前台，未发送输入")
            return
        self._program_probe_game_pid = game_pid
        self._program_probe_game_hwnd = game_window.hwnd
        self._program_probe_started_at_ms = int(time.time() * 1000)
        self._logger.info(
            "step=program_probe.window_ready pid=%s hwnd=%s title=%s",
            game_pid, game_window.hwnd, game_window.title,
        )
        map_identity = MapIdentity(
            str(self._snapshot.metadata.area_id),
            str(self._snapshot.metadata.instance_id),
        )
        role = RoleId("local-device", identity)
        runtime = SimulatedFollowRuntime(
            wall_map=reference.wall_layer,
            map_identity=map_identity,
            arrival_radius=8.0,
            speed_units_per_second=80.0,
            position_ttl_ms=self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            downsample_factor=8,
            # The actor footprint is the hard body clearance. Keep the
            # downsample safety margin small so narrow doors are not inflated
            # twice into impossible walls.
            safety_margin=0,
            clearance_radius=20.0,
            clearance_weight=2.0,
            dead_end_weight=0.75,
            minimum_clearance=0.0,
            footprint_radius=0.0,
            inflate_collision=False,
            stalled_ticks=8,
            # Two visual samples can straddle a doorway transition. Require a
            # longer contact window before escalating to a memory re-anchor.
            contact_required_samples=4,
            local_lookahead=24.0,
            prediction_horizon=0.25,
            closed_loop_controller=ClosedLoopMotionController(
                expected_speed=80.0,
                arrival_radius=8.0,
                max_frame_age_ms=self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            ),
        )
        now_ms = int(time.time() * 1000)
        runtime.add_follower(
            role,
            PositionSample(role, map_identity, current, now_ms, 1.0, "visual"),
            mode=ControlMode.PROGRAM,
        )
        runtime.set_simulated_target(point, now_ms=now_ms)
        self._program_probe_initial_position = tuple(float(value) for value in current)
        self._program_probe_last_position = self._program_probe_initial_position
        self._program_probe_target = tuple(float(value) for value in point)
        self._program_probe_last_observation = None
        self._logger.info(
            "step=program_probe.plan_context map_id=%s map_version=%s role=%s "
            "controller=%s start_native=%s target_native=%s target_display=%s "
            "transform_angle=%s transform_reflect=%s transform_scale=%s transform_translation=%s "
            "wall_shape=%s wall_pixels=%s downsample=%s arrival_radius=%s speed_units_per_second=%s "
            "position_ttl_ms=%s safety_margin=%s clearance_radius=%s clearance_weight=%s "
            "dead_end_weight=%s minimum_clearance=%s footprint_radius=%s collision_inflation=%s",
            map_identity.map_id,
            map_identity.map_version,
            identity,
            self.program_probe_controller_combo.currentData(),
            self._program_probe_initial_position,
            self._program_probe_target,
            self._clicked_target_display,
            getattr(self._dual_map_transform, "angle_degrees", None),
            getattr(self._dual_map_transform, "reflect_horizontal", None),
            getattr(self._dual_map_transform, "scale", None),
            getattr(self._dual_map_transform, "translation", None),
            tuple(int(value) for value in reference.wall_layer.shape),
            int((reference.wall_layer > 0).sum()),
            8,
            8.0,
            80.0,
            self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            0,
            20.0,
            2.0,
            0.75,
            0.0,
            0.0,
            False,
        )
        controller = int(self.program_probe_controller_combo.currentData() or 1)
        output = None
        try:
            output = self.program_output_factory(controller)
            self._program_probe_output = ProgramFollowOutput(
                {role: output}, vector_transform=self._native_route_vector_for_input,
            )
            self._program_probe_output.arm(role)
            self._program_probe_role = role
            self._program_probe_runtime = runtime
            self._program_probe_controller = controller
            self._program_probe_ticks = 0
            self._program_probe_waiting_click = False
            self._program_probe_timer.start()
            self.program_probe_status_label.setText(
                f"控制器 {controller} 已取得租约，持续移动到 ({point[0]:.1f}, {point[1]:.1f})"
            )
            self._logger.info(
                "step=program_probe.acquire_success role=%s controller=%s target=%s",
                role.key,
                controller,
                point,
            )
            self._log_program_probe_diagnostics("acquired")
        except Exception as exc:
            if output is not None:
                try:
                    output.close()
                except Exception:
                    self._logger.exception("step=program_probe.cleanup_failed")
            self._program_probe_output = None
            self.program_probe_status_label.setText(f"程序移动实验失败：{exc}")
            self._logger.exception("step=program_probe.start_failed error=%s", exc)

    def _arm_program_move_probe(self) -> None:
        point = self._program_probe_pending_point
        if point is None:
            return
        self._start_program_move_probe_at(point, _confirmed=True)

    def _tick_program_move_probe(self) -> None:
        output = self._program_probe_output
        runtime = self._program_probe_runtime
        role = self._program_probe_role
        if output is None or runtime is None or role is None:
            self.stop_program_move_probe()
            return
        try:
            now_ms = int(time.time() * 1000)
            if self._program_probe_game_pid is None or not is_process_foreground(
                self._program_probe_game_pid
            ):
                self.stop_program_move_probe(reason="PoE2 已失去前台，已停止真实输入")
                return
            if (
                self._program_probe_started_at_ms is not None
                and now_ms - self._program_probe_started_at_ms > 30_000
            ):
                self.stop_program_move_probe(reason="程序移动实验超过 30 秒，已停止")
                return
            state = self._latest_dual_state
            if state is None:
                self.stop_program_move_probe(reason="人物位置暂时不可用，已停止")
                return
            current_position = state.players.get(role.actor_id)
            if current_position is None:
                if getattr(state, "recovery_requested", False):
                    previous = self._program_probe_last_observation
                    target = self._program_probe_target or getattr(
                        previous, "target_position", None
                    )
                    self._request_program_probe_relocalization(
                        target,
                        reason="视觉 marker 连续丢失，开始内存锚点重定位",
                        diagnostics={"tracker_reason": getattr(state, "reason", None)},
                    )
                else:
                    self.stop_program_move_probe(reason="人物位置暂时不可用，已停止")
                return
            if (
                self._latest_dual_captured_at_ms is None
                or now_ms - self._latest_dual_captured_at_ms > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS
            ):
                self.stop_program_move_probe(reason="视觉定位帧已过期，已停止真实输入")
                return
            # Preserve the capture timestamp.  Reusing ``now_ms`` here would
            # make a frozen visual frame look fresh on every control tick and
            # defeat the runtime's stale-position fail-safe.  The control
            # loop may run faster than the visual worker, so freshness must be
            # measured from the last actual capture.
            visual_captured_at_ms = int(self._latest_dual_captured_at_ms)
            runtime.update_follower_position(
                PositionSample(
                    role,
                    runtime.map_identity,
                    state.players[role.actor_id],
                    visual_captured_at_ms,
                    1.0,
                    "visual",
                )
            )
            runtime.refresh_simulated_target(now_ms=now_ms)
            observation = runtime.tick(now_ms=now_ms)[role.key]
            output.apply(observation, elapsed_ms=50)
            self._update_program_probe_local_contact(state, role, observation)
            self._program_probe_ticks += 1
            self._program_probe_last_observation = observation
            if observation.position is not None:
                self._program_probe_last_position = tuple(observation.position)
            self._render_program_probe_overlay(observation)
            try:
                input_vector = self._native_route_vector_for_input(observation.vector)
            except Exception as transform_error:
                input_vector = None
                self._logger.warning(
                    "step=program_probe.vector_transform_failed tick=%s error=%s",
                    self._program_probe_ticks,
                    transform_error,
                )
            visual_age_ms = (
                None
                if self._latest_dual_captured_at_ms is None
                else max(0, now_ms - self._latest_dual_captured_at_ms)
            )
            self._logger.info(
                "step=program_probe.motion tick=%s coordinate_space=reference_native "
                "current=%s target=%s distance=%s route_length=%s route_detour_ratio=%s "
                "route_points=%s route_end=%s vector_native=%s vector_input=%s "
                "route_chain_points=%s route_collision_segments=%s route_walkable=%s "
                "plan_attempted_factors=%s plan_accepted_factor=%s "
                "plan_candidate_route_count=%s plan_relaxed_candidate_route_count=%s "
                "plan_selected_clearance_mode=%s plan_rejections=%s "
                "plan_start_metrics=%s plan_target_metrics=%s "
                "plan_selected_route_score=%s "
                "plan_selected_route_length=%s "
                "plan_selected_route_minimum_clearance=%s "
                "route_target_shift=%s route_deviation=%s "
                "safety_margin=%s clearance_radius=%s clearance_weight=%s "
                 "dead_end_weight=%s minimum_clearance=%s footprint_radius=%s "
                 "no_progress_ticks=%s direction_mismatch_ticks=%s "
                 "command_observed_alignment=%s command_observed_angle_degrees=%s "
                 "recovery_attempts=%s recovery_candidates_checked=%s "
                 "recovery_selected_index=%s recovery_target=%s "
                "observed_velocity=%s observed_speed=%s local_controller=%s "
                "observed_displacement=%s command_duration_ms=%s "
                "contact_evidence=%s local_obstacle_ahead=%s local_obstacle_distance=%s "
                "local_raw_obstacle_ahead=%s local_escape_available=%s "
                "local_free_left=%s local_free_right=%s relocalization_requested=%s "
                "visual_age_ms=%s capture_at_ms=%s reason=%s state=%s",
                self._program_probe_ticks,
                observation.position,
                observation.target_position,
                observation.distance,
                observation.diagnostics.get("route_length", 0.0),
                float(observation.diagnostics.get("route_length", 0.0))
                / max(float(observation.distance or 0.0), 1e-6),
                len(observation.route),
                observation.route[-1] if observation.route else None,
                tuple(round(float(value), 4) for value in observation.vector),
                None if input_vector is None else tuple(round(float(value), 4) for value in input_vector),
                observation.diagnostics.get("route_chain_points", 0),
                observation.diagnostics.get("route_collision_segments", 0),
                observation.diagnostics.get("route_walkable", False),
                observation.diagnostics.get("plan_attempted_factors", ()),
                observation.diagnostics.get("plan_accepted_factor"),
                observation.diagnostics.get("plan_candidate_route_count", 0),
                observation.diagnostics.get("plan_relaxed_candidate_route_count", 0),
                observation.diagnostics.get("plan_selected_clearance_mode"),
                observation.diagnostics.get("plan_rejections", ()),
                observation.diagnostics.get("plan_start_metrics"),
                observation.diagnostics.get("plan_target_metrics"),
                observation.diagnostics.get("plan_selected_route_score"),
                observation.diagnostics.get("plan_selected_route_length"),
                observation.diagnostics.get("plan_selected_route_minimum_clearance"),
                observation.diagnostics.get("route_target_shift"),
                observation.diagnostics.get("route_deviation"),
                observation.diagnostics.get("route_safety_margin", 0),
                observation.diagnostics.get("route_clearance_radius", 0.0),
                observation.diagnostics.get("route_clearance_weight", 0.0),
                 observation.diagnostics.get("route_dead_end_weight", 0.0),
                 observation.diagnostics.get("route_minimum_clearance", 0.0),
                 observation.diagnostics.get("route_footprint_radius", 0.0),
                 observation.diagnostics.get("no_progress_ticks", 0),
                 observation.diagnostics.get("direction_mismatch_ticks", 0),
                 observation.diagnostics.get("command_observed_alignment"),
                 observation.diagnostics.get("command_observed_angle_degrees"),
                 observation.diagnostics.get("recovery_attempts", 0),
                observation.diagnostics.get("recovery_candidates_checked", 0),
                observation.diagnostics.get("recovery_selected_index"),
                observation.diagnostics.get("recovery_target"),
                observation.diagnostics.get("observed_velocity", (0.0, 0.0)),
                observation.diagnostics.get("observed_speed", 0.0),
                observation.diagnostics.get("local_controller", {}),
                observation.diagnostics.get("observed_displacement", 0.0),
                observation.diagnostics.get("command_duration_ms", 0),
                observation.diagnostics.get("contact_evidence"),
                observation.diagnostics.get("local_obstacle_ahead"),
                observation.diagnostics.get("local_obstacle_distance"),
                observation.diagnostics.get("local_raw_obstacle_ahead"),
                observation.diagnostics.get("local_escape_available", False),
                observation.diagnostics.get("local_free_left"),
                observation.diagnostics.get("local_free_right"),
                observation.diagnostics.get("relocalization_requested", False),
                visual_age_ms,
                self._latest_dual_captured_at_ms,
                observation.reason,
                observation.state.value,
            )
            if self._program_probe_ticks == 1 or self._program_probe_ticks % 5 == 0:
                self._log_program_probe_diagnostics(f"tick={self._program_probe_ticks}")
            self.program_probe_status_label.setText(
                f"移动状态：{observation.state.value} | {observation.reason} | "
                f"距离 {observation.distance if observation.distance is not None else '暂无'}"
            )
            if observation.diagnostics.get("relocalization_requested"):
                self._request_program_probe_relocalization(
                    self._program_probe_target or observation.target_position,
                    reason="小地图连续撞墙，开始内存锚点重定位",
                    diagnostics=dict(observation.diagnostics),
                )
                return
            if observation.state.value in {
                "arrived",
                "blocked",
                "waiting_position",
                "map_mismatch",
            }:
                self.stop_program_move_probe(reason=f"移动结束：{observation.reason}")
        except Exception as exc:
            self._logger.exception("step=program_probe.write_failed error=%s", exc)
            self.program_probe_status_label.setText(f"程序移动输出失败：{exc}")
            self.stop_program_move_probe()

    def _update_program_probe_local_contact(self, state: Any, role: RoleId, observation: Any) -> None:
        """Feed the latest minimap wall beam into the generic follow runtime."""
        runtime = self._program_probe_runtime
        if runtime is not None:
            self._update_follow_local_contact(
                runtime, state, role, observation, log_step="program_probe",
            )

    def _update_follow_local_contact(
        self,
        runtime: SimulatedFollowRuntime,
        state: Any,
        role: RoleId,
        observation: Any,
        *,
        log_step: str,
        emit_log: bool = True,
    ) -> None:
        combined = self._latest_dual_combined
        if combined is None or state is None or state.transform is None:
            return
        screen_position = state.screen_positions.get(role.actor_id)
        if screen_position is None:
            return
        wall_mask = combined[0] if isinstance(combined, (tuple, list)) else combined
        try:
            screen_vector = inverse_transform_local_displacement(
                observation.vector,
                angle_degrees=state.transform.angle_degrees,
                reflect_horizontal=state.transform.reflect_horizontal,
                scale=state.transform.scale,
            )
            contact = inspect_minimap_contact(wall_mask, screen_position, screen_vector)
            runtime.update_local_contact(
                role,
                wall_ahead=contact.wall_ahead,
                blocking_wall_ahead=contact.blocking_wall_ahead,
                escape_available=contact.escape_available,
                wall_distance=contact.wall_distance,
                free_left=contact.free_left,
                free_right=contact.free_right,
                captured_at_ms=self._latest_dual_captured_at_ms,
            )
            if emit_log:
                self._logger.info(
                    "step=%s.local_contact role=%s player_screen=%s "
                    "command_screen=%s raw_wall_ahead=%s blocking_wall_ahead=%s "
                    "centerline_wall_distance=%s narrow_passage=%s wall_distance=%s "
                    "escape_available=%s free_left=%.3f free_right=%.3f",
                    log_step,
                    role.key,
                    tuple(round(float(value), 2) for value in screen_position),
                    tuple(round(float(value), 3) for value in screen_vector),
                    contact.wall_ahead,
                    contact.blocking_wall_ahead,
                    contact.centerline_wall_distance,
                    contact.narrow_passage,
                    contact.wall_distance,
                    contact.escape_available,
                    contact.free_left,
                    contact.free_right,
                )
        except Exception as exc:
            # Contact evidence is advisory.  A malformed/temporarily
            # unavailable minimap frame must not be reported as a Host write
            # failure and must not release the active program lease.
            self._logger.warning(
                "step=%s.local_contact_failed error_type=%s error=%s",
                log_step,
                type(exc).__name__,
                exc,
            )

    def _log_program_probe_diagnostics(self, phase: str) -> None:
        output = self._program_probe_output
        if output is None:
            return
        observation = self._program_probe_last_observation
        if observation is not None:
            self._logger.info(
                "step=program_probe.motion_summary phase=%s state=%s reason=%s "
                "policy=%s complexity_state=%s complexity=%s command_id=%s "
                "command_duration_ms=%s calibration_confidence=%s calibration_samples=%s "
                "calibration_speed_gain=%s",
                phase,
                observation.state.value,
                observation.reason,
                observation.diagnostics.get("motion_loop_policy"),
                observation.diagnostics.get("motion_loop_state"),
                observation.diagnostics.get("motion_loop_complexity"),
                observation.diagnostics.get("motion_loop_command_id"),
                observation.diagnostics.get("command_duration_ms"),
                observation.diagnostics.get("calibration_confidence"),
                observation.diagnostics.get("calibration_samples"),
                observation.diagnostics.get("calibration_speed_gain"),
            )
        try:
            diagnostics = output.diagnostics()
            self._logger.info(
                "step=program_probe.host_final_before_release controller=%s diagnostics=%s",
                self._program_probe_controller,
                diagnostics,
            )
        except Exception as exc:
            self._logger.warning(
                "step=program_probe.host_final_diagnostics_failed controller=%s error=%s",
                self._program_probe_controller,
                exc,
            )
        try:
            diagnostics = output.diagnostics()
        except Exception as exc:
            self._logger.exception("step=program_probe.diagnostics_failed phase=%s error=%s", phase, exc)
            return
        self._logger.info("step=program_probe.%s diagnostics=%s", phase, diagnostics)
        controller_state = diagnostics.get("state", {})
        self.program_probe_status_label.setText(
            f"控制器 {self._program_probe_controller} | lease={diagnostics.get('acquired')} | "
            f"state=({controller_state.get('leftStickX', 0)}, {controller_state.get('leftStickY', 0)})"
        )

    def _render_program_probe_overlay(self, observation: Any | None) -> None:
        """Draw the active program route in the same native/display frame.

        The line deliberately starts at the latest native player sample and
        ends at the exact native target.  This makes a bad route transform
        visible independently of the Xbox output and prevents a display-only
        rotation from hiding a target-distance mismatch.
        """
        state = self._latest_dual_state
        source_size = self._dual_map_source_size
        transform = self._dual_map_transform
        if state is None or source_size is None or transform is None:
            return
        players = {
            str(identity): localization_display_point(
                point, source_size=source_size, transform=transform,
            )
            for identity, point in state.players.items() if point is not None
        }
        routes = {}
        if observation is not None:
            route_points = []
            if observation.position is not None:
                route_points.append(observation.position)
            route_points.extend(observation.route)
            if observation.target_position is not None and (
                not route_points
                or point_distance(route_points[-1], observation.target_position) > 1e-6
            ):
                route_points.append(observation.target_position)
            if len(route_points) >= 2:
                routes[observation.follower.key] = tuple(
                    localization_display_point(
                        point, source_size=source_size, transform=transform,
                    )
                    for point in route_points
                )
        target = self._clicked_target_display
        self.map_widget.set_overlay(players=players, target=target, routes=routes)

    def _clear_program_probe_recovery(self) -> None:
        self._program_probe_recovery_target = None
        self._program_probe_recovery_identity = None
        self._program_probe_recovery_controller = None
        self._program_probe_recovery_started_at_ms = None
        self._program_probe_recovery_attempts = 0

    def _clear_dual_recovery_contexts(self) -> None:
        """Atomically discard every delayed resume owned by this map session."""
        self._clear_program_probe_recovery()
        self._clear_dual_follow_recovery_context()
        self._dual_target_recovery = None
        self._logger.info("step=dual_motion.recovery_contexts_cleared")

    def _save_dual_follow_recovery_context(self) -> None:
        """Keep a visual-follow target while the tracker re-registers."""
        if self._follow_runtime is None or (
            not self._follow_live_mode and self._clicked_target_source is None
        ):
            return
        self._dual_recovery_follow_live = self._follow_live_mode
        self._dual_recovery_follow_instance_id = self._follow_runtime.map_identity.map_version
        self._dual_recovery_follow_radius = self.follow_footprint_radius.value()
        self._dual_recovery_follow_target_source = (
            None if self._follow_live_mode else tuple(self._clicked_target_source)
        )
        self._dual_recovery_follow_p1 = (
            str(self.follow_p1_combo.currentData())
            if self.follow_p1_combo.currentData() is not None else None
        )
        self._dual_recovery_follow_p2 = (
            str(self.follow_p2_combo.currentData())
            if self.follow_p2_combo.currentData() is not None else None
        )
        self._dual_recovery_follow_mode = (
            str(self.follow_mode_combo.currentData())
            if self.follow_mode_combo.currentData() is not None else None
        )
        self._logger.info(
            "step=dual_motion.follow_recovery_context_saved target_source=%s "
            "p1=%s p2=%s mode=%s live=%s instance=%s radius=%s",
            self._dual_recovery_follow_target_source,
            self._dual_recovery_follow_p1,
            self._dual_recovery_follow_p2,
            self._dual_recovery_follow_mode,
            self._dual_recovery_follow_live,
            self._dual_recovery_follow_instance_id,
            self._dual_recovery_follow_radius,
        )

    def _clear_dual_follow_recovery_context(self) -> None:
        self._dual_recovery_follow_target_source = None
        self._dual_recovery_follow_live = False
        self._dual_recovery_follow_instance_id = None
        self._dual_recovery_follow_radius = None
        self._dual_recovery_follow_p1 = None
        self._dual_recovery_follow_p2 = None
        self._dual_recovery_follow_mode = None

    def _save_dual_target_recovery_context(self) -> None:
        if (
            self._dual_target_runtime is None or self._clicked_target_source is None
            or self._snapshot is None or len(self._dual_target_roles) != 2
        ):
            return
        self._dual_target_recovery = (
            self._clicked_target_source,
            self._dual_target_roles[0].actor_id,
            self._dual_target_roles[1].actor_id,
            str(self._snapshot.metadata.instance_id),
        )
        self._logger.info(
            "step=dual_target.recovery_saved context=%s", self._dual_target_recovery,
        )

    def _maybe_resume_dual_target_after_relocalization(self) -> None:
        context = self._dual_target_recovery
        state = self._latest_dual_state
        captured_at_ms = self._latest_dual_captured_at_ms
        if context is None or state is None or self._snapshot is None:
            return
        source, p1, p2, instance_id = context
        if instance_id != str(self._snapshot.metadata.instance_id):
            self._dual_target_recovery = None
            self.dual_target_status_label.setText("双人同目标：地图实例变化，已安全停止")
            return
        if getattr(state, "recovery_requested", False) or state.status != "tracking":
            return
        if captured_at_ms is None or int(time.time() * 1000) - int(captured_at_ms) > 1_000:
            return
        if state.players.get(p1) is None or state.players.get(p2) is None:
            return
        self._dual_target_recovery = None
        for combo, identity in ((self.dual_target_p1_combo, p1), (self.dual_target_p2_combo, p2)):
            index = combo.findData(identity)
            if index < 0:
                self.dual_target_status_label.setText("双人同目标：恢复后角色身份变化，已安全停止")
                return
            combo.setCurrentIndex(index)
        self.start_dual_target_experiment()
        if self._dual_target_runtime is None:
            self._logger.error("step=dual_target.recovery_failed reason=runtime_rebuild")
            return
        self._logger.info("step=dual_target.recovery_resumed target_source=%s", source)
        self._on_follow_map_click(*source)

    def _maybe_resume_dual_follow_after_relocalization(self) -> None:
        target = self._dual_recovery_follow_target_source
        live_mode = self._dual_recovery_follow_live
        state = self._latest_dual_state
        captured_at_ms = self._latest_dual_captured_at_ms
        if (target is None and not live_mode) or state is None or self._snapshot is None:
            return
        if self._dual_recovery_follow_instance_id != str(self._snapshot.metadata.instance_id):
            self._clear_dual_follow_recovery_context()
            self._follow_recovery_pending = True
            self.follow_status_label.setText("实时跟随：地图实例变化，等待重新定位（会话保留）")
            self._logger.warning(
                "step=live_role_follow.recovery_waiting reason=map_instance_changed "
                "follow_session_preserved=True",
            )
            return
        if getattr(state, "recovery_requested", False) or getattr(state, "status", None) != "tracking":
            return
        if captured_at_ms is None or int(time.time() * 1000) - int(captured_at_ms) > (
            self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS if live_mode else 1_000
        ):
            return
        if live_mode and (
            self._dual_recovery_follow_p1 == self._dual_recovery_follow_p2
            or state.players.get(self._dual_recovery_follow_p1) is None
            or state.players.get(self._dual_recovery_follow_p2) is None
        ):
            return
        # A live follow recovery is a non-terminal transition.  Keep the
        # existing runtime/output/session and only replace its visual anchor;
        # calling start_follow_experiment() here would invoke the user-stop
        # lifecycle and make a successful re-anchor look like a stop.
        if live_mode and self._follow_recovery_pending and self._follow_runtime is not None:
            if self._sync_live_follow_from_fresh_frame(
                state,
                captured_at_ms=int(captured_at_ms),
                now_ms=int(time.time() * 1000),
            ):
                self._follow_recovery_pending = False
                self._clear_dual_follow_recovery_context()
                self._follow_stale_since_ms = None
                self._follow_stale_release_sent = False
                self._follow_stale_recovery_requested = False
                self.follow_status_label.setText("实时跟随：视觉恢复完成，继续跟随")
                self._logger.info(
                    "step=live_role_follow.recovery_resumed_in_place "
                    "captured_at_ms=%s session_id=%s",
                    captured_at_ms,
                    self._follow_session_id,
                )
            return
        # Click mode restores its saved point; live mode uses only this fresh
        # frame's selected leader position after rebuilding the runtime.
        if self._dual_recovery_follow_p1 is not None:
            index = self.follow_p1_combo.findData(self._dual_recovery_follow_p1)
            if index >= 0:
                self.follow_p1_combo.setCurrentIndex(index)
        if self._dual_recovery_follow_p2 is not None:
            index = self.follow_p2_combo.findData(self._dual_recovery_follow_p2)
            if index >= 0:
                self.follow_p2_combo.setCurrentIndex(index)
        if self._dual_recovery_follow_mode is not None:
            index = self.follow_mode_combo.findData(self._dual_recovery_follow_mode)
            if index >= 0:
                self.follow_mode_combo.setCurrentIndex(index)
        if self._dual_recovery_follow_radius is not None:
            self.follow_footprint_radius.setValue(self._dual_recovery_follow_radius)
        self.start_follow_experiment(_sync_phase="recovery_sync")
        if self._follow_runtime is None:
            self._logger.error(
                "step=dual_motion.follow_recovery_failed reason=runtime_rebuild_failed "
                "target_source=%s",
                target,
            )
            self._clear_dual_follow_recovery_context()
            return
        self._clear_dual_follow_recovery_context()
        self._logger.info(
            "step=dual_motion.follow_recovery_resumed target_source=%s "
            "captured_at_ms=%s live=%s",
            target,
            captured_at_ms,
            live_mode,
        )
        if not live_mode:
            self._on_follow_map_click(*target)

    def _maybe_resume_program_probe_after_relocalization(self) -> None:
        """Resume the saved target after a fresh dual visual frame arrives."""
        target = self._program_probe_recovery_target
        identity = self._program_probe_recovery_identity
        controller = self._program_probe_recovery_controller
        state = self._latest_dual_state
        captured_at_ms = self._latest_dual_captured_at_ms
        if target is None or identity is None or controller is None or state is None:
            return
        if getattr(state, "recovery_requested", False) or getattr(state, "status", None) != "tracking":
            return
        if captured_at_ms is None or int(time.time() * 1000) - int(captured_at_ms) > 1_000:
            return
        current = state.players.get(identity)
        if current is None:
            return
        role_index = self.program_probe_role_combo.findData(identity)
        controller_index = self.program_probe_controller_combo.findData(controller)
        if role_index < 0 or controller_index < 0:
            self._logger.error(
                "step=program_probe.relocalization_failed reason=selection_missing "
                "role=%s controller=%s",
                identity,
                controller,
            )
            self._clear_program_probe_recovery()
            return
        attempt = self._program_probe_recovery_attempts
        self.program_probe_role_combo.setCurrentIndex(role_index)
        self.program_probe_controller_combo.setCurrentIndex(controller_index)
        self._clear_program_probe_recovery()
        self._logger.info(
            "step=program_probe.relocalization_resumed target=%s role=%s controller=%s "
            "fresh_capture_at_ms=%s current=%s attempt=%s",
            target,
            identity,
            controller,
            captured_at_ms,
            current,
            attempt,
        )
        self._start_program_move_probe_at(target, _confirmed=True)

    def _request_program_probe_relocalization(
        self,
        target: tuple[float, float] | None,
        *,
        reason: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        """Transition program movement into one bounded memory re-anchor."""
        recovery_now_ms = int(time.time() * 1000)
        self._logger.warning(
            "step=program_probe.relocalization_requested reason=%s diagnostics=%s",
            reason,
            diagnostics or {},
        )
        if (
            self._program_probe_last_relocalization_at_ms is not None
            and recovery_now_ms - self._program_probe_last_relocalization_at_ms < 10_000
        ):
            self._logger.warning(
                "step=program_probe.relocalization_cooldown elapsed_ms=%s",
                recovery_now_ms - self._program_probe_last_relocalization_at_ms,
            )
            self.stop_program_move_probe(reason="重定位冷却中，已停止输入等待人工检查")
            return
        if target is None or self._program_probe_role is None:
            self._logger.error(
                "step=program_probe.relocalization_failed reason=missing_resume_context "
                "target=%s role=%s",
                target,
                self._program_probe_role,
            )
            self.stop_program_move_probe(reason="重定位缺少目标上下文，已停止输入")
            return
        self._program_probe_last_relocalization_at_ms = recovery_now_ms
        recovery_identity = self._program_probe_role.actor_id
        recovery_controller = self._program_probe_controller
        self.stop_program_move_probe(reason=reason)
        self._program_probe_recovery_target = tuple(float(value) for value in target)
        self._program_probe_recovery_identity = str(recovery_identity)
        self._program_probe_recovery_controller = int(recovery_controller)
        self._program_probe_recovery_started_at_ms = recovery_now_ms
        self._program_probe_recovery_attempts += 1
        self._logger.info(
            "step=program_probe.relocalization_context_saved target=%s role=%s "
            "controller=%s attempt=%s",
            self._program_probe_recovery_target,
            self._program_probe_recovery_identity,
            self._program_probe_recovery_controller,
            self._program_probe_recovery_attempts,
        )
        if self._dual_motion_tracker is not None:
            self._start_dual_motion(recovery=True)
        else:
            self._logger.error(
                "step=program_probe.relocalization_failed reason=dual_tracker_missing"
            )
            self._clear_program_probe_recovery()

    def stop_program_move_probe(
        self,
        *,
        reason: str | None = None,
        _preserve_recovery: bool = False,
    ) -> None:
        stop_reason = reason or "requested"
        previous_ticks = self._program_probe_ticks
        stopped_at_ms = int(time.time() * 1000)
        elapsed_ms = (
            None
            if self._program_probe_started_at_ms is None
            else max(0, stopped_at_ms - self._program_probe_started_at_ms)
        )
        displacement = None
        if self._program_probe_initial_position is not None and self._program_probe_last_position is not None:
            displacement = (
                self._program_probe_last_position[0] - self._program_probe_initial_position[0],
                self._program_probe_last_position[1] - self._program_probe_initial_position[1],
            )
        last_observation = self._program_probe_last_observation
        self._logger.info(
            "step=program_probe.stop_summary reason=%s ticks=%s elapsed_ms=%s "
            "role=%s controller=%s initial_native=%s last_native=%s target_native=%s "
            "displacement_native=%s final_distance=%s final_state=%s final_reason=%s",
            stop_reason,
            previous_ticks,
            elapsed_ms,
            self._program_probe_role.key if self._program_probe_role is not None else None,
            self._program_probe_controller,
            self._program_probe_initial_position,
            self._program_probe_last_position,
            self._program_probe_target,
            displacement,
            getattr(last_observation, "distance", None),
            getattr(getattr(last_observation, "state", None), "value", None),
            getattr(last_observation, "reason", None),
        )
        self._program_probe_arm_timer.stop()
        self._program_probe_timer.stop()
        self._program_probe_waiting_click = False
        self._program_probe_pending_point = None
        self._program_probe_game_pid = None
        self._program_probe_game_hwnd = None
        self._program_probe_started_at_ms = None
        self._program_probe_initial_position = None
        self._program_probe_last_position = None
        self._program_probe_target = None
        self._program_probe_last_observation = None
        self._program_probe_runtime = None
        self._program_probe_role = None
        if not _preserve_recovery:
            self._clear_program_probe_recovery()
        output, self._program_probe_output = self._program_probe_output, None
        if output is None:
            self.program_probe_stop_button.setEnabled(False)
            self.program_probe_button.setEnabled(True)
            if reason:
                self.program_probe_status_label.setText(reason)
            self._logger.info(
                "step=program_probe.stop reason=%s ticks=%s output_present=False",
                stop_reason,
                previous_ticks,
            )
            return
        try:
            output.release_all()
            self._logger.info("step=program_probe.neutral controller=%s", self._program_probe_controller)
        except Exception:
            self._logger.exception("step=program_probe.neutral_failed")
        finally:
            try:
                output.close_all()
                self._logger.info("step=program_probe.release_success controller=%s", self._program_probe_controller)
            except Exception as exc:
                self._logger.exception("step=program_probe.release_failed error=%s", exc)
        self.program_probe_button.setEnabled(True)
        self.program_probe_stop_button.setEnabled(False)
        self.program_probe_status_label.setText(reason or "测试结束：已发送中性并释放程序租约")
        self._logger.info(
            "step=program_probe.stop reason=%s ticks=%s output_present=True",
            stop_reason,
            previous_ticks,
        )

    def _make_follow_runtime(
        self, reference: Any, map_identity: MapIdentity, *, live_role_follow: bool = False,
    ) -> SimulatedFollowRuntime:
        arrival_radius = 12.0 if live_role_follow else 8.0
        return SimulatedFollowRuntime(
            wall_map=reference.wall_layer,
            map_identity=map_identity,
            arrival_radius=arrival_radius,
            resume_radius=20.0 if live_role_follow else None,
            speed_units_per_second=80.0,
            position_ttl_ms=self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            downsample_factor=8,
            # Narrow native passages remain open; local steering handles contact.
            safety_margin=0,
            clearance_radius=20.0,
            clearance_weight=2.0,
            dead_end_weight=0.75,
            minimum_clearance=0.0,
            footprint_radius=self.follow_footprint_radius.value() if live_role_follow else 0.0,
            inflate_collision=False,
            stalled_ticks=8,
            contact_required_samples=4,
            local_lookahead=24.0,
            prediction_horizon=0.25,
            closed_loop_controller=ClosedLoopMotionController(
                expected_speed=80.0,
                arrival_radius=arrival_radius,
                max_frame_age_ms=self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            ),
        )

    def start_follow_experiment(self, *, _sync_phase: str = "cold_start") -> None:
        """Start a click target or a live role target with explicit output ownership."""
        # The entry point is intentionally idempotent.  Recovery callbacks and
        # rapid UI activation can arrive while an older runtime still owns a
        # timer, output lease, or prediction tracker; release that ownership
        # before constructing the replacement.
        if (
            self._follow_runtime is not None
            or self._follow_timer.isActive()
            or self._follow_program_output is not None
        ):
            self._logger.info("step=follow_experiment.restart_previous_session")
            self.stop_follow_experiment()
        self.stop_dual_target_experiment()
        state = self._latest_dual_state
        reference = self._dual_follow_reference
        if state is None or reference is None or self._dual_map_transform is None:
            self.follow_status_label.setText("跟随实验：请先启动双人实时定位并完成首帧")
            return
        players = {str(identity): point for identity, point in state.players.items() if point is not None}
        if len(players) < 1:
            self.follow_status_label.setText("跟随实验：需要至少一个有效人物位置")
            return
        self._sync_follow_role_choices(state.players)
        p1_identity = self.follow_p1_combo.currentData()
        p2_identity = self.follow_p2_combo.currentData()
        mode = str(self.follow_mode_combo.currentData() or "both")
        live_mode = mode in {"p1_leads", "p2_leads"}
        single_mode = mode in {"single_p1_program", "single_p2_program"}
        if not single_mode and p1_identity == p2_identity:
            self.follow_status_label.setText("跟随实验：请分别选择两个不同且当前有效的 P1/P2 角色")
            return
        now_ms = int(time.time() * 1000)
        self._follow_session_id = f"{now_ms:x}"
        captured_at_ms = self._latest_dual_captured_at_ms
        if live_mode and (
            captured_at_ms is None
            or not 0 <= now_ms - int(captured_at_ms) <= self._FOLLOW_START_MAX_FRAME_AGE_MS
            or state.status != "tracking" or getattr(state, "recovery_requested", False)
            or state.diagnostics.get("warmup_assumed_stationary", False)
        ):
            frame_age_ms = None if captured_at_ms is None else now_ms - int(captured_at_ms)
            self.follow_status_label.setText("跟随实验：等待新鲜双人视觉帧（≤300ms）")
            self._logger.info(
                "step=live_role_follow.start_waiting reason=fresh_frame_required "
                "frame_age_ms=%s max_age_ms=%s status=%s",
                frame_age_ms, self._FOLLOW_START_MAX_FRAME_AGE_MS,
                None if state is None else state.status,
            )
            return
        map_identity = MapIdentity(
            str(self._snapshot.metadata.area_id),
            str(self._snapshot.metadata.instance_id),
        )
        runtime = self._make_follow_runtime(reference, map_identity, live_role_follow=live_mode)
        leader_identity = None
        if live_mode:
            leader_identity = p1_identity if mode == "p1_leads" else p2_identity
            program_identity = p2_identity if mode == "p1_leads" else p1_identity
            selected = (
                (leader_identity, ControlMode.MANUAL),
                (program_identity, ControlMode.PROGRAM),
            )
        elif single_mode:
            selected = ((p1_identity if mode == "single_p1_program" else p2_identity, ControlMode.PROGRAM),)
        else:
            selected = tuple(
                (identity, ControlMode.MANUAL if mode == "p1_manual" and index == 0
                 else ControlMode.PROGRAM if mode == "both_program" else ControlMode.SIMULATED)
                for index, identity in enumerate((p1_identity, p2_identity))
            )
        if any(identity not in players for identity, _control in selected):
            self.follow_status_label.setText("跟随实验：请选择当前有有效位置的受控角色")
            return
        program_roles = tuple(
            RoleId("local-device", identity)
            for identity, control in selected if control is ControlMode.PROGRAM
        )
        if program_roles and self.program_output_factory is None:
            self.follow_status_label.setText("跟随实验：程序控制未绑定虚拟手柄输出")
            return
        self.stop_program_move_probe(reason="已切换到跟随实验")
        outputs: dict[RoleId, Any] = {}
        try:
            for role in program_roles:
                outputs[role] = self.program_output_factory(1 if role.actor_id == p1_identity else 2)
            program_output = (
                ProgramFollowOutput(
                    outputs, vector_transform=self._native_route_vector_for_input,
                )
                if outputs else None
            )
            for identity, control in selected:
                point = players[identity]
                role = RoleId("local-device", identity)
                sample = PositionSample(
                    role, map_identity, point,
                    int(captured_at_ms) if live_mode else now_ms, 1.0, "visual",
                )
                runtime.add_follower(role, sample, mode=control)
        except Exception as exc:
            for output in outputs.values():
                close = getattr(output, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        self._logger.exception("step=follow_experiment.output_cleanup_failed")
            self._follow_program_output = None
            self.follow_status_label.setText(f"跟随实验：虚拟手柄不可用 | {exc}")
            self._logger.exception("step=follow_experiment.output_bind_failed")
            return
        self._follow_program_output = program_output
        self._follow_runtime = runtime
        self._follow_session_id = f"{self._follow_session_id}-{id(runtime):x}"
        self._follow_program_roles = program_roles
        self._follow_role_tracker = (
            CommandRoleTracker(expected_speed=runtime.speed_units_per_second)
            if live_mode else None
        )
        if self._follow_role_tracker is not None:
            for identity, _control in selected:
                self._follow_role_tracker.seed(
                    RoleId("local-device", identity).key, map_identity.map_version,
                    players[identity], captured_at_ms=int(captured_at_ms),
                )
                if live_mode:
                    self._follow_role_tracker.arm_visual_phase(
                        RoleId("local-device", identity).key,
                        started_at_ms=now_ms,
                        grace_ms=self._follow_visual_phase_grace_ms,
                    )
        self._follow_occluded_roles = ()
        self._follow_hold_roles = set()
        self._follow_rejected_visual = {}
        self._follow_recovery_pending = False
        self._follow_recovery_retry_scheduled = False
        self._follow_recovery_retry_delay_ms = 0
        self._follow_recovery_episode_active = False
        self._follow_recovery_episode_reason = None
        self._follow_recovery_episode_suppressed = 0
        self._recovery_controller.clear("follow_started")
        self._follow_live_mode = live_mode
        if live_mode:
            self._enter_live_follow_sync(
                phase=_sync_phase,
                now_ms=now_ms,
                captured_at_ms=int(captured_at_ms),
            )
        else:
            self._follow_sync_phase = "idle"
            self._follow_sync_started_at_ms = None
            self._follow_sync_baseline_captured_at_ms = None
            self._follow_sync_frame_count = 0
            self._follow_sync_last_log_at_ms = None
        self._follow_leader_role = (
            RoleId("local-device", leader_identity) if leader_identity is not None else None
        )
        if live_mode:
            self._publish_follow_prediction_hints()
        self._follow_last_target_log_at_ms = None
        self._follow_last_program_diagnostics_at_ms = None
        self._follow_output_write_counts = {}
        self._follow_target_display = None
        self._last_follow_observations = {}
        self._follow_stale_since_ms = None
        self._follow_stale_release_sent = False
        self._follow_stale_recovery_requested = False
        self._follow_game_pid = None
        self._follow_game_hwnd = None
        self._follow_foreground_wait_started_ms = None
        self._follow_foreground_last_log_at_ms = None
        self._follow_foreground_release_sent = False
        self._follow_foreground_cached_at_ms = None
        self._follow_foreground_cached_result = None
        self._follow_last_visual_positions = {}
        self._follow_last_visual_at_ms = {}
        self._follow_last_evaluated_visual_at_ms = {}
        delay_ms = max(0, int(getattr(self, "_follow_command_arm_delay_ms", 0)))
        self._follow_output_not_before_ms = now_ms + delay_ms
        self._follow_output_delay_last_log_at_ms = None
        self.start_follow_button.setEnabled(False)
        self.stop_follow_button.setEnabled(True)
        for control in (
            self.follow_mode_combo, self.follow_p1_combo, self.follow_p2_combo,
            self.follow_footprint_radius,
        ):
            control.setEnabled(False)
        if live_mode:
            self._clear_clicked_target(reason="live_follow_started")
            if delay_ms:
                self.follow_status_label.setText(
                    f"实时跟随：已启动，{math.ceil(delay_ms / 1000)}秒后允许发送，请切回 PoE2"
                )
            else:
                self.follow_status_label.setText("实时跟随：冷启动同步中，等待新的双人视觉帧")
            self._follow_timer.start()
            self._tick_follow_experiment()
        else:
            mode_text = (
                "真实手柄待命，点击地图后开始接管"
                if program_roles else "仅模拟，不发送真实输入"
            )
            if delay_ms and program_roles:
                mode_text += f"（{math.ceil(delay_ms / 1000)}秒后允许发送）"
            self.follow_status_label.setText(f"跟随实验：已准备，{mode_text}，等待点击地图设置共享目标")
        self._logger.info(
            "step=follow_experiment.armed p1=%s p2=%s mode=%s leader=%s "
            "program_roles=%s footprint_radius=%s visual_phase_grace_ms=%s session_id=%s",
            p1_identity, p2_identity, mode, leader_identity,
            tuple(role.key for role in program_roles), runtime.footprint_radius,
            self._follow_visual_phase_grace_ms if live_mode else 0,
            self._follow_session_id,
        )

    def start_dual_target_experiment(self) -> None:
        """Prepare two independent program outputs for one clicked map target."""
        state = self._latest_dual_state
        reference = self._dual_follow_reference
        if (
            state is None or reference is None or self._dual_map_transform is None
            or self._snapshot is None or self._dual_motion_tracker is None
        ):
            self.dual_target_status_label.setText("双人同目标：请先完成双人实时定位")
            return
        captured_at_ms = self._latest_dual_captured_at_ms
        now_ms = int(time.time() * 1000)
        if captured_at_ms is None or now_ms - int(captured_at_ms) > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS:
            self.dual_target_status_label.setText("双人同目标：视觉位置已过期，请等待新帧")
            return
        if getattr(state, "recovery_requested", False) or state.status != "tracking":
            self.dual_target_status_label.setText("双人同目标：定位尚未稳定")
            return
        players = {str(key): point for key, point in state.players.items() if point is not None}
        self._sync_follow_role_choices(state.players)
        p1 = self.dual_target_p1_combo.currentData()
        p2 = self.dual_target_p2_combo.currentData()
        if p1 not in players or p2 not in players or p1 == p2:
            self.dual_target_status_label.setText("双人同目标：请选择两个不同且当前有效的角色")
            return
        if self.program_output_factory is None:
            self.dual_target_status_label.setText("双人同目标：虚拟手柄输出未绑定")
            return
        self.stop_dual_target_experiment()
        self.stop_follow_experiment()
        self.stop_program_move_probe()
        map_identity = MapIdentity(
            str(self._snapshot.metadata.area_id), str(self._snapshot.metadata.instance_id),
        )
        runtime = self._make_follow_runtime(reference, map_identity)
        roles = (RoleId("local-device", str(p1)), RoleId("local-device", str(p2)))
        outputs = {}
        try:
            outputs[roles[0]] = self.program_output_factory(1)
            outputs[roles[1]] = self.program_output_factory(2)
            output = ProgramFollowOutput(
                outputs, vector_transform=self._native_route_vector_for_input,
            )
        except Exception as exc:
            for bound in outputs.values():
                close = getattr(bound, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        self._logger.exception("step=dual_target.output_cleanup_failed")
            self.dual_target_status_label.setText(f"双人同目标：手柄不可用 | {exc}")
            self._logger.exception("step=dual_target.output_bind_failed")
            return
        for role in roles:
            runtime.add_follower(
                role,
                PositionSample(
                    role, map_identity, players[role.actor_id],
                    int(captured_at_ms), 1.0, "visual",
                ),
                mode=ControlMode.PROGRAM,
            )
        self._dual_target_runtime = runtime
        self._dual_target_output = output
        self._dual_target_roles = roles
        self._dual_target_observations = {}
        self._dual_target_tick_count = 0
        self._dual_target_last_program_diagnostics_at_ms = None
        self.start_dual_target_button.setEnabled(False)
        self.stop_dual_target_button.setEnabled(True)
        self.dual_target_status_label.setText("双人同目标：等待地图点击，尚未发送输入")
        self._logger.info(
            "step=dual_target.ready map=%s roles=%s controllers=(1,2)",
            map_identity, tuple(role.key for role in roles),
        )

    def stop_dual_target_experiment(self, *, _preserve_recovery: bool = False) -> None:
        active = self._dual_target_runtime is not None
        if not _preserve_recovery:
            self._dual_target_recovery = None
        self._dual_target_timer.stop()
        output = self._dual_target_output
        if output is not None:
            try:
                output.close_all()
            except Exception:
                self._logger.exception("step=dual_target.output_close_failed")
        self._dual_target_output = None
        self._dual_target_runtime = None
        self._dual_target_roles = ()
        self._dual_target_observations = {}
        self._dual_target_tick_count = 0
        self._dual_target_last_program_diagnostics_at_ms = None
        if hasattr(self, "start_dual_target_button"):
            self.start_dual_target_button.setEnabled(self._dual_motion_tracker is not None)
            self.stop_dual_target_button.setEnabled(False)
        if active:
            self._clear_clicked_target(reason="dual_target_stopped")
            self.dual_target_status_label.setText("双人同目标：已停止，手柄已释放")
            self._logger.info("step=dual_target.stopped")
            if self._latest_dual_state is not None and self._dual_map_source_size is not None:
                self._render_dual_motion_state(self._latest_dual_state, self._dual_map_source_size)

    def _tick_dual_target_experiment(self) -> None:
        try:
            self._tick_dual_target_experiment_impl()
        except Exception as exc:
            self._logger.exception("step=dual_target.tick_failed error=%s", exc)
            self.stop_dual_target_experiment()
            self.dual_target_status_label.setText(f"双人同目标：运行失败，手柄已释放 | {exc}")

    def _tick_dual_target_experiment_impl(self) -> None:
        runtime = self._dual_target_runtime
        output = self._dual_target_output
        state = self._latest_dual_state
        if runtime is None or output is None:
            return
        if (
            state is None or self._dual_map_transform is None or self._dual_map_source_size is None
            or self._snapshot is None
            or runtime.map_identity.map_id != str(self._snapshot.metadata.area_id)
            or runtime.map_identity.map_version != str(self._snapshot.metadata.instance_id)
        ):
            self._logger.warning("step=dual_target.invalid_map_or_localization")
            self.stop_dual_target_experiment()
            return
        if getattr(state, "recovery_requested", False) or state.status not in {"tracking", "degraded"}:
            output.release_all()
            self._dual_target_observations = {}
            self._render_dual_target_overlay()
            self.dual_target_status_label.setText("双人同目标：定位恢复中，手柄已释放")
            return
        now_ms = int(time.time() * 1000)
        captured_at_ms = self._latest_dual_captured_at_ms
        if captured_at_ms is None or now_ms - int(captured_at_ms) > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS:
            output.release_all()
            self._dual_target_observations = {}
            self._render_dual_target_overlay()
            self.dual_target_status_label.setText("双人同目标：视觉帧过期，手柄已释放")
            return
        runtime.refresh_simulated_target(now_ms=now_ms)
        for role in self._dual_target_roles:
            point = state.players.get(role.actor_id)
            if point is not None:
                runtime.update_follower_position(
                    PositionSample(
                        role, runtime.map_identity, point, int(captured_at_ms), 1.0, "visual",
                    )
                )
        previous_states = {
            key: item.state for key, item in self._dual_target_observations.items()
        }
        observations = runtime.tick(now_ms=now_ms)
        self._dual_target_observations = observations
        self._dual_target_tick_count += 1
        recovery = next(
            (item for item in observations.values()
             if item.diagnostics.get("relocalization_requested")),
            None,
        )
        if recovery is not None:
            if (
                self._dual_target_last_recovery_at_ms is not None
                and now_ms - self._dual_target_last_recovery_at_ms < 10_000
            ):
                self._logger.warning(
                    "step=dual_target.relocalization_cooldown role=%s reason=%s",
                    recovery.follower.key, recovery.reason,
                )
                self.stop_dual_target_experiment()
                self.dual_target_status_label.setText("双人同目标：重定位冷却中，已停止输入")
                return
            self._dual_target_last_recovery_at_ms = now_ms
            self._save_dual_target_recovery_context()
            output.release_all()
            self._logger.warning(
                "step=dual_target.relocalization_requested role=%s reason=%s",
                recovery.follower.key, recovery.reason,
            )
            self._start_dual_motion(recovery=True)
            return
        try:
            for observation in observations.values():
                if (
                    observation.state is FollowState.PROGRAM_READY
                    and not output.is_armed(observation.follower)
                ):
                    output.arm(observation.follower)
                output.apply(observation, elapsed_ms=self._dual_target_timer.interval())
                self._update_follow_local_contact(
                    runtime, state, observation.follower, observation,
                    log_step="dual_target",
                    emit_log=self._dual_target_tick_count == 1 or self._dual_target_tick_count % 5 == 0,
                )
        except Exception as exc:
            self._logger.exception("step=dual_target.output_failed error=%s", exc)
            self.stop_dual_target_experiment()
            self.dual_target_status_label.setText(f"双人同目标：输出失败 | {exc}")
            return
        self._render_dual_target_overlay()
        states = []
        for role in self._dual_target_roles:
            observation = observations.get(role.key)
            if observation is None:
                continue
            if previous_states.get(role.key) is not observation.state:
                self._logger.info(
                    "step=dual_target.state_changed role=%s from=%s to=%s reason=%s",
                    role.key,
                    getattr(previous_states.get(role.key), "value", None),
                    observation.state.value, observation.reason,
                )
            distance = "?" if observation.distance is None else f"{observation.distance:.1f}"
            states.append(f"{role.actor_id}: {observation.state.value} 距离 {distance}")
            if self._dual_target_tick_count == 1 or self._dual_target_tick_count % 5 == 0:
                self._logger.info(
                    "step=dual_target.motion role=%s state=%s reason=%s position=%s "
                    "target=%s distance=%s route_points=%s vector=%s "
                    "route_length=%s command_ms=%s recovery=%s",
                    role.key, observation.state.value, observation.reason,
                    observation.position, observation.target_position, observation.distance,
                    len(observation.route), observation.vector,
                    observation.diagnostics.get("route_length"),
                    observation.diagnostics.get("command_duration_ms"),
                    observation.diagnostics.get("recovery_attempts"),
                )
        self.dual_target_status_label.setText("双人同目标：" + " | ".join(states))
        if (
            self._dual_target_tick_count == 1
            or self._dual_target_last_program_diagnostics_at_ms is None
            or now_ms - self._dual_target_last_program_diagnostics_at_ms
            >= self._PROGRAM_DIAGNOSTICS_INTERVAL_MS
        ):
            self._dual_target_last_program_diagnostics_at_ms = now_ms
            try:
                self._logger.info(
                    "step=dual_target.output_diagnostics controllers=%s", output.diagnostics(),
                )
            except Exception as exc:
                self._logger.warning("step=dual_target.diagnostics_failed error=%s", exc)
        if len(observations) == 2 and all(
            item.state is FollowState.ARRIVED for item in observations.values()
        ):
            self._dual_target_timer.stop()
            self._logger.info("step=dual_target.both_arrived target=%s", runtime.remote.position)

    def _render_dual_target_overlay(self) -> None:
        state = self._latest_dual_state
        source_size = self._dual_map_source_size
        transform = self._dual_map_transform
        if state is None or source_size is None or transform is None:
            return
        players = {
            str(identity): localization_display_point(
                point, source_size=source_size, transform=transform,
            )
            for identity, point in state.players.items() if point is not None
        }
        routes = {}
        for key, observation in self._dual_target_observations.items():
            points = ([observation.position] if observation.position is not None else [])
            points.extend(observation.route)
            if len(points) >= 2:
                routes[key] = tuple(
                    localization_display_point(
                        point, source_size=source_size, transform=transform,
                    ) for point in points
                )
        self.map_widget.set_overlay(
            players=players, target=self._clicked_target_display, routes=routes,
        )

    def _native_route_vector_for_input(
        self, vector: tuple[float, float]
    ) -> tuple[float, float]:
        """Keep route vectors in the canonical native frame for game input.

        Registration is already applied when source/display coordinates are
        converted to the reference/native map.  Applying its inverse again
        here would rotate or mirror the Xbox direction a second time.  The
        gamepad adapter owns the only native-to-stick projection.
        """
        if self._dual_map_transform is None:
            raise RuntimeError("map orientation is unavailable for program movement")
        return native_route_vector_for_program_output(vector)

    def stop_follow_experiment(
        self, *, _preserve_recovery: bool = False, reason: str = "requested",
    ) -> None:
        reason = self._follow_stop_reason or reason
        self._follow_stop_reason = None
        self._follow_recovery_pending = False
        self._follow_recovery_episode_active = False
        self._follow_recovery_episode_reason = None
        self._follow_recovery_episode_suppressed = 0
        was_active = self._follow_runtime is not None or self._follow_timer.isActive()
        was_live = self._follow_live_mode
        had_timer = self._follow_timer.isActive()
        had_output = self._follow_program_output is not None
        stop_context = {
            "session_id": self._follow_session_id,
            "reason": reason,
            "sync_phase": self._follow_sync_phase,
            "tick_count": self._follow_tick_count,
            "tick_attempt_count": self._follow_tick_attempt_count,
            "rejected_visual": dict(self._follow_rejected_visual),
            "occluded_roles": tuple(self._follow_occluded_roles),
            "hold_roles": tuple(sorted(self._follow_hold_roles)),
            "last_visual_positions": dict(self._follow_last_visual_positions),
            "last_evaluated_visual_at_ms": dict(self._follow_last_evaluated_visual_at_ms),
            "foreground": {
                "pid": self._follow_game_pid,
                "hwnd": self._follow_game_hwnd,
                "wait_started_ms": self._follow_foreground_wait_started_ms,
                "release_sent": self._follow_foreground_release_sent,
            },
            "output_not_before_ms": self._follow_output_not_before_ms,
            "output_snapshot": (
                None if self._follow_program_output is None
                else self._follow_program_output.snapshot()
                if callable(getattr(self._follow_program_output, "snapshot", None))
                else None
            ),
        }
        if not _preserve_recovery:
            self._clear_dual_follow_recovery_context()
        self._follow_timer.stop()
        worker = self._dual_motion_worker
        if worker is not None:
            worker.set_prediction_hints({}, generation=worker.generation)
        if self._follow_program_output is not None:
            try:
                self._follow_program_output.close_all()
            except Exception:
                self._logger.exception("step=follow_experiment.output_close_failed")
        self._follow_program_output = None
        self._follow_role_tracker = None
        self._follow_program_roles = ()
        self._follow_occluded_roles = ()
        self._follow_hold_roles = set()
        self._follow_rejected_visual = {}
        self._follow_last_evaluated_visual_at_ms = {}
        self._follow_leader_role = None
        self._follow_live_mode = False
        self._follow_sync_phase = "idle"
        self._follow_sync_started_at_ms = None
        self._follow_sync_baseline_captured_at_ms = None
        self._follow_sync_frame_count = 0
        self._follow_sync_last_log_at_ms = None
        self._follow_last_target_log_at_ms = None
        self._follow_tick_count = 0
        self._follow_tick_attempt_count = 0
        self._follow_session_id = None
        self._follow_last_program_diagnostics_at_ms = None
        self._follow_stale_since_ms = None
        self._follow_stale_release_sent = False
        self._follow_stale_recovery_requested = False
        self._follow_output_not_before_ms = None
        self._follow_output_delay_last_log_at_ms = None
        self._follow_game_pid = None
        self._follow_game_hwnd = None
        self._follow_foreground_wait_started_ms = None
        self._follow_foreground_last_log_at_ms = None
        self._follow_foreground_release_sent = False
        self._follow_foreground_cached_at_ms = None
        self._follow_foreground_cached_result = None
        self._follow_runtime = None
        self._follow_target_display = None
        self._last_follow_observations = {}
        self.start_follow_button.setEnabled(self._dual_motion_tracker is not None)
        self.stop_follow_button.setEnabled(False)
        for control in (
            self.follow_mode_combo, self.follow_p1_combo, self.follow_p2_combo,
            self.follow_footprint_radius,
        ):
            control.setEnabled(True)
        self._sync_follow_radius_control()
        self._clear_clicked_target(reason="follow_stopped")
        if was_active:
            if self._latest_dual_state is not None and self._dual_map_source_size is not None:
                self._render_dual_motion_state(self._latest_dual_state, self._dual_map_source_size)
            else:
                self.map_widget.clear_overlay()
            self._logger.info(
                "step=follow_experiment.stopped live=%s preserve_recovery=%s "
                "timer_active=%s output_present=%s context=%s "
                "last_observations=%s",
                was_live,
                _preserve_recovery,
                had_timer,
                had_output,
                stop_context,
                {
                    key: {
                        "state": getattr(value.state, "value", value.state),
                        "reason": value.reason,
                        "distance": value.distance,
                    }
                    for key, value in self._last_follow_observations.items()
                },
            )
            self.follow_status_label.setText(
                "实时跟随：已停止，程序手柄已释放" if was_live else "跟随实验：已停止"
            )

    def _clear_clicked_target(self, *, reason: str) -> None:
        """Clear the user-click marker and record why it disappeared."""
        had_target = self._clicked_target_display is not None
        self._clicked_target_source = None
        self._clicked_target_native = None
        self._clicked_target_display = None
        self.map_widget.set_target(None)
        if had_target:
            self._logger.info("step=map_click.cleared reason=%s", reason)

    def _on_follow_map_click(self, display_x: float, display_y: float) -> None:
        if self._follow_runtime is not None and self._follow_live_mode:
            self._logger.info("step=live_role_follow.map_click_ignored reason=target_is_live_role")
            return
        source_size = self._dual_map_source_size
        transform = self._dual_map_transform
        reference = self._dual_follow_reference
        source_click = (float(display_x), float(display_y))
        self._logger.info(
            "step=map_click.received source_space=source_pixmap x=%.1f y=%.1f",
            *source_click,
        )
        if source_size is None or transform is None or reference is None:
            self._logger.warning(
                "step=map_click.rejected reason=missing_localization_context "
                "source=(%.1f,%.1f) source_size=%s has_transform=%s has_reference=%s",
                *source_click,
                source_size,
                transform is not None,
                reference is not None,
            )
            if self._dual_target_runtime is not None:
                self.stop_dual_target_experiment()
                self.dual_target_status_label.setText("双人同目标：定位坐标失效，已停止输入")
            return
        try:
            point = localization_source_point(
                source_click, source_size=source_size, transform=transform,
            )
            display_point = localization_display_point(
                point, source_size=source_size, transform=transform,
            )
            round_trip_error = math.hypot(
                display_point[0] - source_click[0],
                display_point[1] - source_click[1],
            )
        except Exception as exc:
            self._logger.exception(
                "step=map_click.rejected reason=coordinate_transform_failed "
                "source=(%.1f,%.1f) error=%s",
                *source_click,
                exc,
            )
            if self._dual_target_runtime is not None:
                self.stop_dual_target_experiment()
                self.dual_target_status_label.setText(f"双人同目标：坐标转换失败，已停止输入 | {exc}")
            else:
                self.follow_status_label.setText(f"地图点击：坐标转换失败 | {exc}")
            return
        height, width = reference.wall_layer.shape[:2]
        if not (0.0 <= point[0] < width and 0.0 <= point[1] < height):
            if self._dual_target_runtime is None:
                self._clicked_target_source = None
                self._clicked_target_native = None
                self._clicked_target_display = None
                self.map_widget.set_target(None)
            self._logger.warning(
                "step=map_click.rejected reason=out_of_bounds source=(%.1f,%.1f) "
                "native=(%.3f,%.3f) bounds=(0,0,%s,%s) round_trip_error=%.4f",
                *source_click,
                point[0], point[1],
                width, height,
                round_trip_error,
            )
            if self._dual_target_runtime is not None:
                self.dual_target_status_label.setText("双人同目标：无效点击，仍前往上一目标")
            else:
                self.follow_status_label.setText("跟随实验：点击位置超出当前地图")
            return
        self._clicked_target_source = source_click
        self._clicked_target_native = (float(point[0]), float(point[1]))
        self._clicked_target_display = (float(display_point[0]), float(display_point[1]))
        self.map_widget.set_target(self._clicked_target_display)
        mode = "program_probe" if self._program_probe_waiting_click else (
            "dual_target" if self._dual_target_runtime is not None else (
                "follow" if self._follow_runtime is not None else "display_only"
            )
        )
        self._logger.info(
            "step=map_click.transformed mode=%s source_space=source_pixmap "
            "source=(%.1f,%.1f) native=(%.3f,%.3f) display=(%.3f,%.3f) "
            "round_trip_error=%.4f angle=%.3f reflect_horizontal=%s scale=%.6f "
            "translation=%s map_size=%s bounds=(0,0,%s,%s)",
            mode,
            *source_click,
            point[0], point[1],
            display_point[0], display_point[1],
            round_trip_error,
            getattr(transform, "angle_degrees", None),
            getattr(transform, "reflect_horizontal", None),
            getattr(transform, "scale", None),
            getattr(transform, "translation", None),
            source_size,
            width,
            height,
        )
        self._logger.info(
            "step=map_click.accepted mode=%s target_displayed=True native=(%.3f,%.3f)",
            mode,
            point[0],
            point[1],
        )
        selected_role = (
            self.program_probe_role_combo.currentData()
            if mode == "program_probe" and hasattr(self, "program_probe_role_combo")
            else None
        )
        selected_position = (
            None
            if self._latest_dual_state is None or selected_role is None
            else self._latest_dual_state.players.get(str(selected_role))
        )
        players_native = (
            {}
            if self._latest_dual_state is None
            else dict(self._latest_dual_state.players)
        )
        self._logger.info(
            "step=map_click.target_context mode=%s selected_role=%s current_native=%s players_native=%s "
            "target_native=%s target_display=%s wall_pixels=%s",
            mode,
            selected_role,
            selected_position,
            players_native,
            point,
            self._clicked_target_display,
            int((reference.wall_layer > 0).sum()),
        )
        if self._program_probe_waiting_click:
            self._start_program_move_probe_at(point)
            return
        if self._dual_target_runtime is not None:
            runtime = self._dual_target_runtime
            now_ms = int(time.time() * 1000)
            try:
                runtime.set_simulated_target(point, now_ms=now_ms)
                self._dual_target_timer.start()
                self._logger.info(
                    "step=dual_target.target_changed native=%s display=%s roles=%s",
                    point, self._clicked_target_display,
                    tuple(role.key for role in self._dual_target_roles),
                )
                self._tick_dual_target_experiment()
            except Exception as exc:
                self._logger.exception("step=dual_target.target_failed error=%s", exc)
                self.stop_dual_target_experiment()
                self.dual_target_status_label.setText(f"双人同目标：目标执行失败 | {exc}")
            return
        runtime = self._follow_runtime
        if runtime is None:
            self.follow_status_label.setText(
                f"地图点击：已显示目标 ({point[0]:.1f}, {point[1]:.1f})，等待跟随实验"
            )
            return
        now_ms = int(time.time() * 1000)
        runtime.set_simulated_target(point, now_ms=now_ms)
        try:
            # Do not arm directly from the click callback.  The shared tick
            # owns the complete boundary: foreground check -> six-second
            # handoff delay -> runtime decision -> arm/write.  Arming here
            # used to bypass that delay whenever the first target was clicked.
            if not self._follow_timer.isActive():
                self._follow_timer.start()
            self._follow_target_display = self._clicked_target_display
            self.follow_status_label.setText(
                f"跟随实验：目标已设置 ({point[0]:.1f}, {point[1]:.1f})，正在规划安全路线"
            )
            self._logger.info(
                "step=follow_experiment.target_changed native=(%.3f,%.3f) "
                "display=(%.3f,%.3f) source=(%.1f,%.1f) round_trip_error=%.4f",
                point[0], point[1],
                self._clicked_target_display[0], self._clicked_target_display[1],
                source_click[0], source_click[1],
                round_trip_error,
            )
            self._logger.info(
                "step=follow_experiment.target_context map_id=%s map_version=%s "
                "follower_roles=%s wall_shape=%s wall_pixels=%s",
                runtime.map_identity.map_id,
                runtime.map_identity.map_version,
                (
                    self.follow_p1_combo.currentData(),
                    self.follow_p2_combo.currentData(),
                ),
                tuple(int(value) for value in reference.wall_layer.shape),
                int((reference.wall_layer > 0).sum()),
            )
            self._tick_follow_experiment()
        except Exception as exc:
            self._logger.exception("step=follow_experiment.output_failed")
            self._continue_follow_after_runtime_failure(
                f"target_output_exception:{type(exc).__name__}", exc,
            )
            return

    def _tick_follow_experiment(self) -> None:
        started = time.perf_counter()
        attempt = self._follow_tick_attempt_count + 1
        try:
            self._follow_tick_attempt_count = attempt
            self._tick_follow_experiment_impl()
        except Exception as exc:
            self._logger.exception("step=follow_experiment.tick_failed error=%s", exc)
            self._continue_follow_after_runtime_failure(
                f"tick_exception:{type(exc).__name__}", exc,
            )
        finally:
            self._logger.debug(
            "step=follow_experiment.tick_dispatch_end attempt=%s elapsed_ms=%.3f "
                "active=%s timer_active=%s live=%s session_id=%s",
                attempt,
                (time.perf_counter() - started) * 1000.0,
                self._follow_runtime is not None,
                self._follow_timer.isActive(),
                self._follow_live_mode,
                self._follow_session_id,
            )

    def _continue_follow_after_runtime_failure(
        self, reason: str, error: Exception | None = None,
    ) -> None:
        """Convert a transient follow fault into a retryable paused tick.

        The follow timer and runtime remain alive. Releasing the current
        output is only a neutral safety state while the next tick retries; it
        is not a terminal follow result and must never call
        ``stop_follow_experiment``.
        """
        if self._follow_program_output is not None:
            try:
                self._follow_program_output.release_all()
            except Exception:
                self._logger.exception("step=follow_experiment.recovery_release_failed reason=%s", reason)
        if self._follow_live_mode and self._follow_runtime is not None:
            self._follow_recovery_pending = True
            self.follow_status_label.setText("实时跟随：暂时异常，保持会话并继续重试")
            self._schedule_live_follow_recovery_retry(reason)
        elif self._follow_runtime is not None:
            self.follow_status_label.setText("跟随实验：暂时异常，保持会话并继续重试")
        else:
            self.follow_status_label.setText("跟随实验：暂时异常，等待下一次有效状态")
        self._logger.warning(
            "step=follow_experiment.continues_after_error reason=%s "
            "runtime_present=%s timer_active=%s live=%s error=%s",
            reason,
            self._follow_runtime is not None,
            self._follow_timer.isActive(),
            self._follow_live_mode,
            error,
        )

    def _current_follow_prediction_hints(
        self, now_ms: int,
    ) -> dict[str, tuple[float, float, float, int]]:
        tracker = self._follow_role_tracker
        if tracker is None or not self._follow_live_mode:
            return {}
        hints = {}
        roles = (self._follow_leader_role, *self._follow_program_roles)
        for role in roles:
            if role is None:
                continue
            try:
                estimate = tracker.estimate(role.key, now_ms=now_ms)
            except (KeyError, ValueError):
                continue
            age_ms = now_ms - estimate.last_visual_at_ms
            if age_ms > (
                3000 if role == self._follow_leader_role else self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS
            ) and (
                role == self._follow_leader_role or not tracker.has_output_since_visual(role.key)
            ):
                continue
            if estimate.uncertainty_native > 12.0:
                continue
            hints[role.actor_id] = (
                *estimate.position, estimate.uncertainty_native, now_ms,
            )
        return hints

    def _publish_follow_prediction_hints(self) -> None:
        worker = self._dual_motion_worker
        if worker is not None:
            worker.set_prediction_hints(
                self._current_follow_prediction_hints(int(time.time() * 1000)),
                generation=worker.generation,
            )

    def _refresh_follow_game_window(self) -> tuple[bool, str]:
        """Return whether live-follow input may be consumed by PoE2.

        The virtual-gamepad Host is independent from desktop focus: it can
        accept and submit a report while the workbench is foreground.  The
        game, however, may not consume that report until its own window is
        active.  Keep this check at the business boundary so a stale visual
        marker is never mistaken for a localization failure.

        ``_follow_foreground_check_override`` is an internal test seam for
        page tests that use fake output objects without a real PoE2 process.
        """
        override = self._follow_foreground_check_override
        if override is not None:
            return bool(override), "test_override"
        now_ms = int(time.time() * 1000)
        cached_at_ms = self._follow_foreground_cached_at_ms
        cached_result = self._follow_foreground_cached_result
        if (
            cached_at_ms is not None
            and cached_result is not None
            and now_ms - cached_at_ms < self._FOLLOW_FOREGROUND_CACHE_MS
        ):
            return cached_result
        try:
            pid = int(find_process_id())
            window = find_process_window(pid, title_substring="Path of Exile 2")
        except Exception as exc:
            self._logger.warning(
                "step=live_role_follow.foreground_check_failed error=%s", exc,
            )
            self._follow_game_pid = None
            self._follow_game_hwnd = None
            result = (False, "window_lookup_failed")
            self._follow_foreground_cached_at_ms = now_ms
            self._follow_foreground_cached_result = result
            return result
        if window is None:
            self._follow_game_pid = pid
            self._follow_game_hwnd = None
            result = (False, "window_not_found")
            self._follow_foreground_cached_at_ms = now_ms
            self._follow_foreground_cached_result = result
            return result
        self._follow_game_pid = pid
        self._follow_game_hwnd = int(window.hwnd)
        if not is_process_foreground(pid):
            result = (False, "poe2_not_foreground")
        else:
            result = (True, "foreground")
        self._follow_foreground_cached_at_ms = now_ms
        self._follow_foreground_cached_result = result
        return result

    def _gate_live_follow_foreground(
        self, *, state: Any, captured_at_ms: int | None, now_ms: int,
    ) -> bool:
        """Hold live-follow output until the game is the foreground process.

        The gate is deliberately a wait state.  It releases any existing
        lease, keeps visual tracking alive, and resets the visual anchor after
        focus returns.  It never requests global re-localization merely
        because the workbench had focus.
        """
        allowed, reason = self._refresh_follow_game_window()
        if allowed:
            was_waiting = self._follow_foreground_wait_started_ms is not None
            if was_waiting:
                self._logger.info(
                    "step=live_role_follow.foreground_resumed wait_ms=%s pid=%s hwnd=%s",
                    max(0, now_ms - int(self._follow_foreground_wait_started_ms)),
                    self._follow_game_pid,
                    self._follow_game_hwnd,
                )
                self._follow_foreground_wait_started_ms = None
                self._follow_foreground_last_log_at_ms = None
                self._follow_foreground_release_sent = False
                # Re-seed from the newest complete frame before arming.  This
                # removes any prediction history accumulated while waiting and
                # gives the first post-focus command a fresh visual baseline.
                if (
                    state is not None
                    and captured_at_ms is not None
                    and self._follow_role_tracker is not None
                    and self._sync_live_follow_from_fresh_frame(
                        state, captured_at_ms=int(captured_at_ms), now_ms=now_ms,
                    )
                ):
                    self._logger.info(
                        "step=live_role_follow.foreground_baseline_reset captured_at_ms=%s",
                        captured_at_ms,
                    )
            return True

        if self._follow_program_output is not None and not self._follow_foreground_release_sent:
            try:
                self._follow_program_output.release_all()
                self._follow_foreground_release_sent = True
            except Exception:
                self._logger.exception(
                    "step=live_role_follow.foreground_release_failed",
                )
        if self._follow_foreground_wait_started_ms is None:
            self._follow_foreground_wait_started_ms = now_ms
            self._follow_foreground_last_log_at_ms = None
        if (
            self._follow_foreground_last_log_at_ms is None
            or now_ms - self._follow_foreground_last_log_at_ms
            >= self._FOLLOW_FOREGROUND_LOG_INTERVAL_MS
        ):
            self._follow_foreground_last_log_at_ms = now_ms
            waited_ms = now_ms - self._follow_foreground_wait_started_ms
            self._logger.warning(
                "step=live_role_follow.waiting_game_foreground reason=%s "
                "waited_ms=%s timeout_ms=%s pid=%s hwnd=%s",
                reason, waited_ms, self._FOLLOW_FOREGROUND_WAIT_MS,
                self._follow_game_pid, self._follow_game_hwnd,
            )
        waited_ms = now_ms - self._follow_foreground_wait_started_ms
        if waited_ms >= self._FOLLOW_FOREGROUND_WAIT_MS:
            self.follow_status_label.setText(
                "实时跟随：请切回 PoE2 窗口后再继续，当前未发送手柄输入"
            )
        else:
            self.follow_status_label.setText(
                f"实时跟随：等待 PoE2 前台窗口（{max(0, self._FOLLOW_FOREGROUND_WAIT_MS - waited_ms) // 1000}s）"
            )
        return False

    @staticmethod
    def _is_normal_follow_hold(observation: FollowObservation) -> bool:
        """Return whether a zero/idle observation is an expected hold state.

        Live role follow starts while the two local roles are often already
        together.  The runtime deliberately suppresses output inside the
        arrival/resume band.  In that state a zero vector is healthy and must
        not be promoted to a relocalization request merely because the
        follower marker is temporarily occluded.
        """
        return observation.state is FollowState.ARRIVED or observation.reason in {
            "within_arrival_radius",
            "within_resume_radius",
            "arrival_unconfirmed",
            "target_arrival_unconfirmed",
        }

    @classmethod
    def _visual_continuity_limit(cls, elapsed_ms: int) -> float:
        """Return the maximum trusted marker step for one fresh frame."""
        elapsed = max(0, int(elapsed_ms))
        return min(
            cls._FOLLOW_VISUAL_CONTINUITY_MAX_STEP,
            max(6.0, cls._FOLLOW_VISUAL_CONTINUITY_MAX_SPEED * elapsed / 1000.0),
        )

    def _tick_follow_experiment_impl(self) -> None:
        tick_attempt = self._follow_tick_attempt_count
        tick_started = time.perf_counter()
        runtime = self._follow_runtime
        source_size = self._dual_map_source_size
        transform = self._dual_map_transform
        self._logger.debug(
            "step=follow_experiment.tick_begin attempt=%s completed_tick=%s "
            "live=%s sync_phase=%s runtime=%s source_size=%s transform=%s "
            "program_roles=%s armed=%s output_not_before_ms=%s session_id=%s",
            tick_attempt,
            self._follow_tick_count,
            self._follow_live_mode,
            self._follow_sync_phase,
            runtime is not None,
            source_size,
            transform is not None,
            tuple(role.key for role in self._follow_program_roles),
            None if self._follow_program_output is None else self._follow_program_output.snapshot(),
            self._follow_output_not_before_ms,
            self._follow_session_id,
        )
        if runtime is None or source_size is None or transform is None:
            self._logger.warning(
                "step=follow_experiment.tick_end attempt=%s outcome=missing_context "
                "runtime=%s source_size=%s transform=%s",
                tick_attempt, runtime is not None, source_size, transform is not None,
            )
            if runtime is not None and self._follow_live_mode:
                self._follow_recovery_pending = True
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                self.follow_status_label.setText("实时跟随：地图变换暂时不可用，跟随会话继续")
                self._schedule_live_follow_recovery_retry("tick_map_context_missing")
            return
        now_ms = int(time.time() * 1000)
        state = self._latest_dual_state
        live_samples: dict[str, PositionSample] = {}
        live_sync_pending = False
        self._logger.debug(
            "step=follow_experiment.tick_context attempt=%s now_ms=%s "
            "state_status=%s state_recovery=%s captured_at_ms=%s frame_age_ms=%s "
            "latest_players=%s state_diagnostics_summary=%s",
            tick_attempt,
            now_ms,
            None if state is None else state.status,
            None if state is None else getattr(state, "recovery_requested", False),
            self._latest_dual_captured_at_ms,
            None if self._latest_dual_captured_at_ms is None else now_ms - int(self._latest_dual_captured_at_ms),
            {} if state is None else dict(state.players),
            {} if state is None else {
                key: state.diagnostics.get(key)
                for key in (
                    "warmup_assumed_stationary", "wall_trusted", "visible_identities",
                    "missing_identities", "marker_dropout_failures", "recovery_reason",
                )
                if key in state.diagnostics
            },
        )
        # A program lease is only useful when the game can consume it.  Apply
        # the same foreground boundary to click-target follow as to live-role
        # follow; otherwise a map click made while the workbench is focused
        # arms the Host lease and immediately creates prediction drift.
        if self._follow_program_roles and not self._gate_live_follow_foreground(
            state=state,
            captured_at_ms=self._latest_dual_captured_at_ms,
            now_ms=now_ms,
        ):
            self._logger.debug(
                "step=follow_experiment.tick_end attempt=%s outcome=waiting_foreground "
                "foreground=%s pid=%s hwnd=%s",
                tick_attempt,
                self._follow_foreground_wait_started_ms is not None,
                self._follow_game_pid,
                self._follow_game_hwnd,
            )
            return
        not_before_ms = self._follow_output_not_before_ms
        if self._follow_program_roles and not_before_ms is not None and now_ms < not_before_ms:
            remaining_ms = max(0, int(not_before_ms) - now_ms)
            if (
                self._follow_output_delay_last_log_at_ms is None
                or now_ms - self._follow_output_delay_last_log_at_ms
                >= self._FOLLOW_COMMAND_ARM_LOG_INTERVAL_MS
            ):
                self._follow_output_delay_last_log_at_ms = now_ms
                self._logger.info(
                    "step=follow_experiment.command_delay_waiting remaining_ms=%s "
                    "not_before_ms=%s program_roles=%s",
                    remaining_ms,
                    not_before_ms,
                    tuple(role.key for role in self._follow_program_roles),
                )
            seconds = math.ceil(remaining_ms / 1000)
            prefix = "实时跟随" if self._follow_live_mode else "跟随实验"
            self.follow_status_label.setText(
                f"{prefix}：等待 {seconds} 秒后发送指令，请切回 PoE2"
            )
            self._logger.debug(
                "step=follow_experiment.tick_end attempt=%s outcome=command_delay "
                "remaining_ms=%s not_before_ms=%s",
                tick_attempt, remaining_ms, not_before_ms,
            )
            return
        if self._follow_program_roles and not_before_ms is not None:
            self._follow_output_not_before_ms = None
            self._follow_output_delay_last_log_at_ms = None
            self._logger.info(
                "step=follow_experiment.command_delay_elapsed program_roles=%s",
                tuple(role.key for role in self._follow_program_roles),
            )
        if self._follow_live_mode:
            captured_at_ms = self._latest_dual_captured_at_ms
            leader = self._follow_leader_role
            if (
                state is None or leader is None or self._snapshot is None
                or runtime.map_identity.map_id != str(self._snapshot.metadata.area_id)
                or runtime.map_identity.map_version != str(self._snapshot.metadata.instance_id)
            ):
                self._follow_recovery_pending = True
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                self.follow_status_label.setText("实时跟随：等待地图/定位上下文恢复，跟随会话继续")
                self._schedule_live_follow_recovery_retry("tick_live_context_changed")
                return
            roles = (leader, *self._follow_program_roles)
            role_tracker = self._follow_role_tracker
            role_observations = state.diagnostics.get("role_observations", {})
            frame_age_ms = None if captured_at_ms is None else now_ms - int(captured_at_ms)
            frame_is_stale = (
                captured_at_ms is None
                or frame_age_ms > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS
            ) and not self._follow_recovery_pending
            warmup_assumed_stationary = bool(
                state.diagnostics.get("warmup_assumed_stationary", False)
            )
            if frame_is_stale:
                if self._follow_stale_since_ms is None:
                    self._follow_stale_since_ms = now_ms
                if not self._follow_stale_release_sent:
                    if self._follow_program_output is not None:
                        self._follow_program_output.release_all()
                    self._follow_stale_release_sent = True
                    self._logger.warning(
                        "step=live_role_follow.waiting status=%s frame_age_ms=%s leader=%s",
                        state.status, frame_age_ms, leader.key,
                    )
                stale_duration_ms = now_ms - self._follow_stale_since_ms
                if (
                    stale_duration_ms >= self._FOLLOW_STALE_RECOVERY_AFTER_MS
                    and not self._follow_stale_recovery_requested
                ):
                    self._follow_stale_recovery_requested = True
                    self._logger.warning(
                        "step=live_role_follow.visual_frame_stalled duration_ms=%s "
                        "frame_age_ms=%s recovery_after_ms=%s",
                        stale_duration_ms, frame_age_ms,
                        self._FOLLOW_STALE_RECOVERY_AFTER_MS,
                    )
                    self._request_live_follow_reanchor("visual_frame_stalled")
                    self._logger.warning(
                        "step=follow_experiment.tick_end attempt=%s outcome=reanchor "
                        "reason=visual_frame_stalled frame_age_ms=%s stale_duration_ms=%s",
                        tick_attempt, frame_age_ms, stale_duration_ms,
                    )
                    return
                self.follow_status_label.setText("实时跟随：等待可信双人位置，手柄已释放")
                return
            if self._follow_stale_since_ms is not None:
                self._logger.info(
                    "step=live_role_follow.visual_frame_resumed stale_duration_ms=%s",
                    max(0, now_ms - self._follow_stale_since_ms),
                )
                self._follow_stale_since_ms = None
                self._follow_stale_release_sent = False
                self._follow_stale_recovery_requested = False
            if role_tracker is None or warmup_assumed_stationary:
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                self.follow_status_label.setText("实时跟随：等待可信双人位置，手柄已释放")
                self._logger.warning(
                    "step=live_role_follow.waiting status=%s frame_age_ms=%s leader=%s",
                    state.status, frame_age_ms, leader.key,
                )
                self._logger.info(
                    "step=follow_experiment.tick_end attempt=%s outcome=waiting_role_tracker "
                    "status=%s frame_age_ms=%s warmup=%s",
                    tick_attempt, state.status, frame_age_ms, warmup_assumed_stationary,
                )
                return
            if (
                not self._follow_recovery_pending
                and (
                getattr(state, "recovery_requested", False)
                or state.status not in {"tracking", "degraded"}
                or (state.status == "degraded" and not state.diagnostics.get("wall_trusted", False))
                )
            ):
                self._logger.warning(
                    "step=follow_experiment.tick_end attempt=%s outcome=reanchor "
                    "reason=wall_or_identity_tracking_lost status=%s recovery_requested=%s "
                    "diagnostics=%s",
                    tick_attempt, state.status, getattr(state, "recovery_requested", False),
                    state.diagnostics,
                )
                self._request_live_follow_reanchor("wall_or_identity_tracking_lost")
                return
            if self._follow_sync_phase in {"cold_start", "recovery_sync"} and not self._follow_recovery_pending:
                baseline = self._follow_sync_baseline_captured_at_ms
                has_new_frame = (
                    baseline is not None and int(captured_at_ms) > int(baseline)
                )
                if not has_new_frame:
                    live_sync_pending = True
                    if (
                        self._follow_sync_last_log_at_ms is None
                        or now_ms - self._follow_sync_last_log_at_ms
                        >= self._FOLLOW_COLD_START_LOG_INTERVAL_MS
                    ):
                        self._follow_sync_last_log_at_ms = now_ms
                        self._logger.info(
                            "step=live_role_follow.sync_waiting phase=%s "
                            "baseline_captured_at_ms=%s captured_at_ms=%s "
                            "frame_age_ms=%s",
                            self._follow_sync_phase,
                            baseline,
                            captured_at_ms,
                            frame_age_ms,
                        )
                    if self._follow_program_output is not None:
                        self._follow_program_output.release_all()
                    self.follow_status_label.setText(
                        "实时跟随：冷启动同步中，等待新的双人视觉帧"
                    )
                elif not self._sync_live_follow_from_fresh_frame(
                    state, captured_at_ms=int(captured_at_ms), now_ms=now_ms,
                ):
                    live_sync_pending = True
                    if self._follow_program_output is not None:
                        self._follow_program_output.release_all()
                    self.follow_status_label.setText(
                        "实时跟随：冷启动同步中，等待完整双人视觉帧"
                    )
            self._logger.debug(
                "step=live_role_follow.frame_inputs attempt=%s tick=%s "
                "captured_at_ms=%s frame_age_ms=%s phase=%s roles=%s",
                tick_attempt,
                self._follow_tick_count + 1,
                captured_at_ms,
                frame_age_ms,
                self._follow_sync_phase,
                {
                    role.key: {
                        "visible": (
                            bool(role_observations.get(role.actor_id, {}).get("visible", False))
                            if isinstance(role_observations.get(role.actor_id), dict) else None
                        ),
                        "point": state.players.get(role.actor_id),
                        "previous_visual": self._follow_last_visual_positions.get(role.key),
                        "rejected_count": self._follow_rejected_visual.get(role.key, 0),
                    }
                    for role in roles
                },
            )
            occluded = []
            for role in roles:
                info = role_observations.get(role.actor_id)
                visible = (
                    bool(info.get("visible")) if isinstance(info, dict)
                    else state.status == "tracking" and state.players.get(role.actor_id) is not None
                )
                point = state.players.get(role.actor_id)
                if visible and point is not None:
                    # The leader is manually controlled.  Its movement is the
                    # target signal, so a large visual displacement is valid
                    # and must never be judged against command odometry from
                    # the follower's virtual stick.  Keep the tracker anchor
                    # fresh for temporary occlusion, but reserve innovation
                    # rejection/re-anchor decisions for program roles.
                    if role == leader:
                        previous_leader = self._follow_last_visual_positions.get(role.key)
                        if (
                            previous_leader is not None
                            and point_distance(point, previous_leader) > 12.0
                        ):
                            self._logger.info(
                                "step=live_role_follow.manual_leader_visual_move "
                                "role=%s previous=%s current=%s displacement=%.3f "
                                "captured_at_ms=%s accepted_without_innovation_gate=True",
                                role.key,
                                previous_leader,
                                point,
                                point_distance(point, previous_leader),
                                captured_at_ms,
                            )
                        role_tracker.seed(
                            role.key,
                            runtime.map_identity.map_version,
                            (float(point[0]), float(point[1])),
                            captured_at_ms=int(captured_at_ms),
                        )
                        if self._follow_tick_count <= 2 or self._follow_tick_count % 20 == 0:
                            self._logger.info(
                                "step=live_role_follow.manual_leader_visual_accept "
                                "role=%s point=%s captured_at_ms=%s "
                                "innovation_gate=bypassed",
                                role.key, point, captured_at_ms,
                            )
                        self._follow_rejected_visual.pop(role.key, None)
                        self._follow_last_visual_positions[role.key] = (
                            float(point[0]), float(point[1]),
                        )
                        self._follow_last_visual_at_ms[role.key] = int(captured_at_ms)
                        self._follow_last_evaluated_visual_at_ms[role.key] = int(captured_at_ms)
                        live_samples[role.actor_id] = PositionSample(
                            role,
                            runtime.map_identity,
                            (float(point[0]), float(point[1])),
                            int(captured_at_ms),
                            1.0,
                            "visual",
                        )
                        continue
                    estimate = role_tracker.estimate(role.key, now_ms=max(now_ms, int(captured_at_ms)))
                    duplicate_visual_frame = False
                    if int(captured_at_ms) < estimate.last_visual_at_ms:
                        duplicate_visual_frame = True
                        if self._follow_tick_count % 10 == 0:
                            self._logger.info(
                                "step=live_role_follow.visual_old_frame_skipped "
                                "role=%s captured_at_ms=%s last_visual_at_ms=%s",
                                role.key, captured_at_ms, estimate.last_visual_at_ms,
                            )
                    elif int(captured_at_ms) == estimate.last_visual_at_ms:
                        self._follow_last_evaluated_visual_at_ms[role.key] = int(captured_at_ms)
                        live_samples[role.actor_id] = PositionSample(
                            role, runtime.map_identity,
                            role_tracker.estimate(role.key, now_ms=int(captured_at_ms)).position,
                            int(captured_at_ms), 1.0, "visual",
                        )
                        continue
                    elif int(captured_at_ms) > estimate.last_visual_at_ms:
                        last_evaluated_at_ms = self._follow_last_evaluated_visual_at_ms.get(
                            role.key,
                        )
                        if (
                            last_evaluated_at_ms is not None
                            and int(captured_at_ms) <= int(last_evaluated_at_ms)
                        ):
                            duplicate_visual_frame = True
                            # This is the same frame that was already
                            # accepted, rebased, or rejected on an earlier
                            # timer tick.  Keep bounded command odometry and
                            # wait for a newer capture; never increment the
                            # rejection episode again.
                            if self._follow_tick_count % 10 == 0:
                                self._logger.info(
                                    "step=live_role_follow.visual_duplicate_skipped "
                                    "role=%s captured_at_ms=%s last_evaluated_at_ms=%s "
                                    "last_visual_at_ms=%s",
                                    role.key,
                                    captured_at_ms,
                                    last_evaluated_at_ms,
                                    estimate.last_visual_at_ms,
                                )
                        else:
                            self._follow_last_evaluated_visual_at_ms[role.key] = int(
                                captured_at_ms
                            )
                            phase_active = role_tracker.visual_phase_active(
                                role.key, now_ms=int(captured_at_ms),
                            )
                            last_visual = self._follow_last_visual_positions.get(role.key)
                            last_visual_at_ms = self._follow_last_visual_at_ms.get(role.key)
                            unchanged_visual_during_output = (
                                last_visual is not None
                                and point_distance(point, last_visual) <= 1.5
                                and role_tracker.has_output_since_visual(role.key)
                            )
                            if unchanged_visual_during_output:
                                # A screenshot can repeat the last marker while a
                                # recently submitted stick pulse is still being
                                # consumed.  Keep bounded command odometry alive;
                                # counting this as an innovation rejection caused
                                # the three-frame re-anchor loop.
                                estimate = role_tracker.estimate(
                                    role.key, now_ms=max(now_ms, int(captured_at_ms)),
                                )
                                self._follow_rejected_visual.pop(role.key, None)
                                live_samples[role.actor_id] = PositionSample(
                                    role, runtime.map_identity, estimate.position, now_ms,
                                    max(0.5, 1.0 - estimate.uncertainty_native / 30.0),
                                    "command_prediction",
                                )
                                if self._follow_tick_count == 1 or self._follow_tick_count % 5 == 0:
                                    self._logger.info(
                                        "step=live_role_follow.visual_hold role=%s point=%s "
                                        "predicted=%s visual_age_ms=%s "
                                        "reason=unchanged_marker_after_output",
                                        role.key, point, estimate.position,
                                        max(0, int(captured_at_ms) - estimate.last_visual_at_ms),
                                    )
                                continue
                            estimate = role_tracker.observe(
                                role.key, runtime.map_identity.map_version, point,
                                captured_at_ms=int(captured_at_ms),
                            )
                            if not estimate.accepted_observation:
                                previous_visual = self._follow_last_visual_positions.get(role.key)
                                elapsed_visual_ms = int(captured_at_ms) - int(estimate.last_visual_at_ms)
                                visual_step = (
                                    None if previous_visual is None else
                                    point_distance(previous_visual, point)
                                )
                                continuity_limit = self._visual_continuity_limit(elapsed_visual_ms)
                                self._logger.info(
                                    "step=live_role_follow.visual_continuity_check role=%s "
                                    "previous_visual=%s point=%s predicted=%s "
                                    "estimate_last_visual_at_ms=%s captured_at_ms=%s "
                                    "page_last_visual_at_ms=%s elapsed_ms=%s visual_step=%s "
                                    "limit=%s continuity_max_gap_ms=%s frame_max_age_ms=%s",
                                    role.key,
                                    previous_visual,
                                    point,
                                    estimate.position,
                                    estimate.last_visual_at_ms,
                                    captured_at_ms,
                                    last_visual_at_ms,
                                    elapsed_visual_ms,
                                    visual_step,
                                    continuity_limit,
                                    self._FOLLOW_VISUAL_CONTINUITY_MAX_GAP_MS,
                                    self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
                                )
                                if (
                                    previous_visual is not None
                                    and last_visual_at_ms == estimate.last_visual_at_ms
                                    and 0 < elapsed_visual_ms <= self._FOLLOW_VISUAL_CONTINUITY_MAX_GAP_MS
                                    and visual_step is not None
                                    and visual_step <= continuity_limit
                                ):
                                    predicted_position = estimate.position
                                    estimate = role_tracker.rebase_visual(
                                        role.key,
                                        runtime.map_identity.map_version,
                                        (float(point[0]), float(point[1])),
                                        captured_at_ms=int(captured_at_ms),
                                        reason="visual_continuity_rebase",
                                    )
                                    self._follow_rejected_visual.pop(role.key, None)
                                    self._follow_last_visual_positions[role.key] = (
                                        float(point[0]), float(point[1]),
                                    )
                                    self._follow_last_visual_at_ms[role.key] = int(captured_at_ms)
                                    if not self._follow_recovery_pending:
                                        self._clear_live_follow_recovery_episode(
                                            "visual_continuity_rebase",
                                        )
                                    self._logger.info(
                                        "step=live_role_follow.visual_continuity_rebase "
                                        "role=%s point=%s predicted=%s innovation=%.3f "
                                        "visual_step=%.3f elapsed_ms=%s limit=%.3f "
                                        "estimated_speed=%.3f",
                                        role.key,
                                        point,
                                        predicted_position,
                                        point_distance(point, predicted_position),
                                        visual_step,
                                        elapsed_visual_ms,
                                        continuity_limit,
                                        role_tracker.diagnostics(
                                            role.key, now_ms=int(captured_at_ms)
                                        )["estimated_speed"],
                                    )
                    if not duplicate_visual_frame and (
                        estimate.accepted_observation or estimate.reason == "duplicate_visual"
                    ):
                        self._follow_rejected_visual.pop(role.key, None)
                        if not self._follow_recovery_pending:
                            self._clear_live_follow_recovery_episode("visual_accepted")
                        self._follow_last_visual_positions[role.key] = (
                            float(point[0]), float(point[1]),
                        )
                        self._follow_last_visual_at_ms[role.key] = int(captured_at_ms)
                        live_samples[role.actor_id] = PositionSample(
                            role, runtime.map_identity, point, int(captured_at_ms), 1.0, "visual",
                        )
                        continue
                    if duplicate_visual_frame:
                        # Fall through to the bounded command prediction below.
                        # This frame has already been accounted for and must
                        # never increment the rejection episode again.
                        pass
                    else:
                        rejected_count = self._follow_rejected_visual.get(role.key, 0) + 1
                        if phase_active:
                            # Startup/recovery frames can legitimately precede the
                            # acknowledged stick pulse.  Do not carry these
                            # transient rejects into the steady-state reanchor
                            # counter.
                            self._follow_rejected_visual[role.key] = 0
                        else:
                            self._follow_rejected_visual[role.key] = rejected_count
                        self._logger.warning(
                            "step=live_role_follow.visual_rejected role=%s point=%s "
                            "predicted=%s innovation=%.3f uncertainty=%.3f reason=%s "
                            "phase_active=%s rejected_count=%s reanchor_after=%s",
                            role.key, point, estimate.position,
                            point_distance(point, estimate.position),
                            estimate.uncertainty_native, estimate.reason,
                            phase_active, self._follow_rejected_visual[role.key],
                            self._FOLLOW_REJECTED_VISUAL_REANCHOR_COUNT,
                        )
                        if (
                            not phase_active
                            and self._follow_rejected_visual[role.key]
                            >= self._FOLLOW_REJECTED_VISUAL_REANCHOR_COUNT
                        ):
                            self._request_live_follow_reanchor("repeated_visual_innovation_rejected")
                            return
                occluded.append(role.actor_id)
                estimate = role_tracker.estimate(role.key, now_ms=max(now_ms, int(captured_at_ms)))
                visual_age_ms = now_ms - estimate.last_visual_at_ms
                if role == leader:
                    if visual_age_ms > 3000:
                        self._request_live_follow_reanchor("manual_target_unobserved")
                        return
                    source = "target_hold"
                else:
                    if estimate.uncertainty_native > 12.0 or (
                        visual_age_ms > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS
                        and not role_tracker.has_output_since_visual(role.key)
                    ):
                        self._request_live_follow_reanchor("command_prediction_unbounded")
                        return
                    source = "command_prediction"
                live_samples[role.actor_id] = PositionSample(
                    role, runtime.map_identity, estimate.position, now_ms,
                    max(0.5, 1.0 - estimate.uncertainty_native / 30.0), source,
                )
                if self._follow_tick_count % 10 == 0 or role.actor_id not in self._follow_occluded_roles:
                    self._logger.info(
                        "step=live_role_follow.prediction role=%s source=%s native=%s "
                        "uncertainty=%.3f visual_age_ms=%s output_since_visual=%s",
                        role.key, source, estimate.position, estimate.uncertainty_native,
                        visual_age_ms, role_tracker.has_output_since_visual(role.key),
                    )
            occluded = tuple(occluded)
            if occluded != self._follow_occluded_roles:
                self._logger.info(
                    "step=live_role_follow.observation roles=%s occluded=%s age_uncertainty=%s",
                    tuple(role.actor_id for role in roles), occluded,
                    {role: (role_observations.get(role, {}).get("age_ms"),
                            role_observations.get(role, {}).get("uncertainty_native"))
                     for role in occluded},
                )
                self._follow_occluded_roles = occluded
            tracker_time_ms = max(now_ms, int(captured_at_ms))
            tracker_estimates = {
                role.key: role_tracker.estimate(role.key, now_ms=tracker_time_ms)
                for role in roles
            }
            compact_tracker = {
                role_key: {
                    "estimate": estimate.position,
                    "uncertainty_native": estimate.uncertainty_native,
                    "last_visual_at_ms": estimate.last_visual_at_ms,
                    "source": estimate.source,
                }
                for role_key, estimate in tracker_estimates.items()
            }
            if tick_attempt % 5 == 0:
                tracker_snapshots = {
                    role.key: role_tracker.diagnostics(
                        role.key, now_ms=tracker_time_ms
                    )
                    for role in roles
                }
                self._logger.info(
                    "step=live_role_follow.tracker_state attempt=%s tick=%s now_ms=%s roles=%s",
                    tick_attempt, self._follow_tick_count + 1, now_ms,
                    tracker_snapshots,
                )
            else:
                self._logger.debug(
                    "step=live_role_follow.tracker_compact attempt=%s tick=%s roles=%s",
                    tick_attempt, self._follow_tick_count + 1, compact_tracker,
                )
            sample = live_samples[leader.actor_id]
            previous_target = runtime.remote.position
            if runtime.set_target_sample(sample) is not None and (
                previous_target is None
                or point_distance(previous_target.position, sample.position) >= 8.0
                or self._follow_last_target_log_at_ms is None
                or now_ms - self._follow_last_target_log_at_ms >= 1000
            ):
                self._follow_last_target_log_at_ms = now_ms
                self._logger.info(
                    "step=live_role_follow.target role=%s native=%s captured_at_ms=%s age_ms=%s",
                    leader.key, sample.position, sample.captured_at_ms,
                    now_ms - sample.captured_at_ms,
                )
        else:
            runtime.refresh_simulated_target(now_ms=now_ms)
        if state is not None and self._follow_live_mode:
            for role in (self._follow_leader_role, *self._follow_program_roles):
                if role is None:
                    continue
                runtime.update_follower_position(live_samples[role.actor_id])
        elif state is not None:
            visual_captured_at_ms = self._latest_dual_captured_at_ms
            # Do not stamp an old visual position with the control tick time.
            # Doing so made a stalled/late tracker look fresh forever and the
            # gamepad kept driving from a position that had never been
            # observed.  Synthetic page tests without a capture timestamp
            # retain the old immediate-preview behavior.
            if visual_captured_at_ms is None:
                visual_captured_at_ms = now_ms
            for role_key, point in state.players.items():
                role = RoleId("local-device", str(role_key))
                try:
                    follower_mode = runtime.mode_for(role)
                except KeyError:
                    follower_mode = None
                if follower_mode in (ControlMode.MANUAL, ControlMode.PROGRAM) and point is not None:
                    runtime.update_follower_position(
                        PositionSample(
                            role,
                            runtime.map_identity,
                            point,
                            int(visual_captured_at_ms),
                            0.7 if self._follow_live_mode and role_key in self._follow_occluded_roles else 1.0,
                            "wall_estimate" if self._follow_live_mode and role_key in self._follow_occluded_roles else "visual",
                        )
                    )
        observations = runtime.tick(now_ms=now_ms)
        self._last_follow_observations = observations
        self._follow_tick_count += 1
        self._logger.debug(
            "step=follow_experiment.runtime_decision attempt=%s tick=%s now_ms=%s "
            "target=%s observations=%s",
            tick_attempt,
            self._follow_tick_count,
            now_ms,
            None if runtime.remote.position is None else runtime.remote.position.position,
            {
                role_key: {
                    "state": item.state.value,
                    "reason": item.reason,
                    "position": item.position,
                    "target": item.target_position,
                    "distance": item.distance,
                    "vector": item.vector,
                    "route_length": item.diagnostics.get("route_length"),
                    "command_duration_ms": item.diagnostics.get("command_duration_ms"),
                    "observed_displacement": item.diagnostics.get("observed_displacement"),
                    "observed_speed": item.diagnostics.get("observed_speed"),
                    "no_progress_ticks": item.diagnostics.get("no_progress_ticks"),
                    "recovery_attempts": item.diagnostics.get("recovery_attempts"),
                    "local_controller_summary": {
                        key: item.diagnostics.get("local_controller", {}).get(key)
                        for key in (
                            "reason", "policy", "state", "motion_loop_state",
                            "motion_loop_command_id", "observed_speed", "speed_ratio",
                            "no_progress_ticks", "recovery_attempts",
                        )
                        if key in item.diagnostics.get("local_controller", {})
                    },
                }
                for role_key, item in observations.items()
            },
        )
        if self._follow_live_mode:
            hold_roles = {
                role.actor_id
                for role in self._follow_program_roles
                if self._is_normal_follow_hold(observations[role.key])
            }
            if hold_roles != self._follow_hold_roles:
                self._logger.info(
                    "step=live_role_follow.hold_state roles=%s previous=%s "
                    "details=%s",
                    tuple(sorted(hold_roles)),
                    tuple(sorted(self._follow_hold_roles)),
                    {
                        role.actor_id: {
                            "state": observations[role.key].state.value,
                            "reason": observations[role.key].reason,
                            "distance": observations[role.key].distance,
                            "arrival_radius": runtime.arrival_radius,
                            "resume_radius": runtime.resume_radius,
                        }
                        for role in self._follow_program_roles
                        if role.actor_id in hold_roles
                    },
                )
            self._follow_hold_roles = hold_roles
            recovery = None if live_sync_pending else next(
                (item for item in observations.values()
                 if item.diagnostics.get("relocalization_requested")), None,
            )
            if recovery is not None and not self._follow_recovery_pending:
                self._logger.warning(
                    "step=live_role_follow.relocalization_requested role=%s reason=%s",
                    recovery.follower.key, recovery.reason,
                )
                self._save_dual_follow_recovery_context()
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                self._logger.warning(
                    "step=follow_experiment.tick_end attempt=%s outcome=relocalization "
                    "role=%s reason=%s observation=%s",
                    tick_attempt, recovery.follower.key, recovery.reason, recovery.diagnostics,
                )
                self._start_dual_motion(recovery=True)
                return
            # A follower that is inside the arrival/resume band is expected
            # to produce a zero vector.  It may also be represented by a
            # command prediction while its marker is hidden.  Neither case
            # means that the map anchor is lost; wait for the leader to move
            # beyond resume_radius and let the normal runtime transition back
            # to PROGRAM_READY.
            # An occluded role with a zero vector is not sufficient evidence
            # for global recovery.  In particular, a valid character can be
            # reported on a wall cell when the native/map transform is one
            # grid off; the motion diagnostics may still say
            # ``progress_observed``.  Re-anchor only when the movement layer
            # explicitly reports contact/no-progress recovery evidence.
            unsafe_occluded_roles = []
            for role in self._follow_program_roles:
                observation = observations[role.key]
                contact = observation.diagnostics.get("contact_evidence") or {}
                if not isinstance(contact, Mapping):
                    contact = {}
                if (
                    role.actor_id in self._follow_occluded_roles
                    and not self._is_normal_follow_hold(observation)
                    and (
                        observation.diagnostics.get("relocalization_requested", False)
                        or bool(contact.get("recovery_required", False))
                    )
                ):
                    unsafe_occluded_roles.append(role)
            if not live_sync_pending and not self._follow_recovery_pending and unsafe_occluded_roles:
                self._logger.warning(
                    "step=follow_experiment.tick_end attempt=%s outcome=reanchor "
                    "reason=occluded_role_has_no_safe_candidate occluded=%s observations=%s",
                    tick_attempt,
                    tuple(role.actor_id for role in unsafe_occluded_roles),
                    observations,
                )
                self._request_live_follow_reanchor("occluded_role_has_no_safe_candidate")
                return
            if (
                not live_sync_pending
                and not self._follow_recovery_pending
                and self._follow_occluded_roles
                and not unsafe_occluded_roles
            ):
                self._logger.info(
                    "step=live_role_follow.occlusion_held reason=no_recovery_evidence "
                    "occluded=%s",
                    self._follow_occluded_roles,
                )
        if self._follow_program_output is not None and not live_sync_pending:
            try:
                for role in self._follow_program_roles:
                    observation = observations[role.key]
                    was_armed = self._follow_program_output.is_armed(role)
                    self._logger.debug(
                        "step=live_role_follow.output_decision attempt=%s tick=%s role=%s "
                        "state=%s reason=%s armed=%s vector=%s command_duration_ms=%s "
                        "distance=%s target=%s occluded=%s",
                        tick_attempt,
                        self._follow_tick_count,
                        role.key,
                        observation.state.value,
                        observation.reason,
                        was_armed,
                        observation.vector,
                        observation.diagnostics.get("command_duration_ms"),
                        observation.distance,
                        observation.target_position,
                        role.actor_id in self._follow_occluded_roles,
                    )
                    if (
                        observation.state is FollowState.PROGRAM_READY
                        and not self._follow_program_output.is_armed(role)
                    ):
                        self._follow_program_output.arm(role)
                        self._logger.info(
                            "step=live_role_follow.output_armed role=%s",
                            role.key,
                        )
                    receipt = self._follow_program_output.apply(
                        observation, elapsed_ms=self._follow_timer.interval(),
                    )
                    self._logger.debug(
                        "step=live_role_follow.output_result attempt=%s tick=%s role=%s "
                        "state=%s armed_after=%s receipt=%s local_output=%s",
                        tick_attempt,
                        self._follow_tick_count,
                        role.key,
                        observation.state.value,
                        self._follow_program_output.is_armed(role),
                        None if receipt is None else {
                            "accepted_at_ms": receipt.accepted_at_ms,
                            "effective_input_vector": receipt.effective_input_vector,
                            "effective_axes": receipt.effective_axes,
                            "ttl_ms": receipt.ttl_ms,
                        },
                        self._follow_program_output.snapshot(),
                    )
                    if self._follow_live_mode and receipt is not None and self._follow_role_tracker is not None:
                        write_count = self._follow_output_write_counts.get(role.key, 0) + 1
                        self._follow_output_write_counts[role.key] = write_count
                        if write_count <= 3 or write_count % 5 == 0:
                            self._logger.info(
                                "step=live_role_follow.output_accepted role=%s count=%s "
                                "accepted_at_ms=%s ttl_ms=%s effective_input=%s effective_axes=%s",
                                role.key, write_count, receipt.accepted_at_ms, receipt.ttl_ms,
                                receipt.effective_input_vector, receipt.effective_axes,
                            )
                        if getattr(receipt, "ttl_ms", 0) > 0:
                            calibration = (
                                runtime.closed_loop_controller.calibrator.state_for(role.key)
                                if runtime.closed_loop_controller is not None else None
                            )
                            self._follow_role_tracker.record_output(
                                role.key, receipt.effective_input_vector,
                                accepted_at_ms=receipt.accepted_at_ms,
                                ttl_ms=receipt.ttl_ms,
                                speed_gain=1.0 if calibration is None else calibration.speed_gain,
                                calibration_confidence=0.0 if calibration is None else calibration.confidence,
                            )
                    if self._follow_live_mode and role.actor_id not in self._follow_occluded_roles:
                        self._update_follow_local_contact(
                            runtime, state, role, observation, log_step="live_role_follow",
                            emit_log=self._follow_tick_count == 1 or self._follow_tick_count % 5 == 0,
                        )
            except Exception as exc:
                self._logger.exception("step=follow_experiment.program_output_failed error=%s", exc)
                self._continue_follow_after_runtime_failure(
                    f"program_output_exception:{type(exc).__name__}", exc,
                )
                return
        elif self._follow_program_output is not None and live_sync_pending:
            self._follow_program_output.release_all()
        if tick_attempt % 5 == 0:
            self._logger.info(
            "step=follow_experiment.diagnostic_snapshot attempt=%s tick=%s "
            "sync_phase=%s frame_age_ms=%s live_sync_pending=%s target=%s "
                "observations=%s output_snapshot=%s session_id=%s",
                tick_attempt,
                self._follow_tick_count,
                self._follow_sync_phase,
                None if self._latest_dual_captured_at_ms is None else now_ms - int(self._latest_dual_captured_at_ms),
                live_sync_pending,
                None if runtime.remote.position is None else runtime.remote.position.position,
                {
                    role_key: {
                        "state": item.state.value,
                        "reason": item.reason,
                        "position": item.position,
                        "target": item.target_position,
                        "distance": item.distance,
                        "vector": item.vector,
                        "command_duration_ms": item.diagnostics.get("command_duration_ms"),
                        "observed_displacement": item.diagnostics.get("observed_displacement"),
                        "observed_speed": item.diagnostics.get("observed_speed"),
                        "no_progress_ticks": item.diagnostics.get("no_progress_ticks"),
                        "recovery_attempts": item.diagnostics.get("recovery_attempts"),
                    }
                    for role_key, item in observations.items()
                },
                None if self._follow_program_output is None else self._follow_program_output.snapshot(),
                self._follow_session_id,
            )
        if self._follow_tick_count == 1 or self._follow_tick_count % 5 == 0:
            motion_details = {}
            for role_key, item in observations.items():
                try:
                    input_vector = self._native_route_vector_for_input(item.vector)
                except Exception as transform_error:
                    input_vector = None
                    self._logger.warning(
                        "step=follow_experiment.vector_transform_failed role=%s tick=%s error=%s",
                        role_key,
                        self._follow_tick_count,
                        transform_error,
                    )
                motion_details[role_key] = {
                    "state": item.state.value,
                    "reason": item.reason,
                    "coordinate_space": item.diagnostics.get("coordinate_space", "unknown"),
                    "current_native": item.position,
                    "target_native": item.target_position,
                    "distance": item.distance,
                    "route_length": item.diagnostics.get("route_length", 0.0),
                    "route_detour_ratio": (
                        float(item.diagnostics.get("route_length", 0.0))
                        / max(float(item.distance or 0.0), 1e-6)
                    ),
                    "route_chain_points": item.diagnostics.get("route_chain_points", 0),
                    "route_collision_segments": item.diagnostics.get("route_collision_segments", 0),
                    "route_walkable": item.diagnostics.get("route_walkable", False),
                    "plan_attempted_factors": item.diagnostics.get("plan_attempted_factors", ()),
                    "plan_accepted_factor": item.diagnostics.get("plan_accepted_factor"),
                    "plan_candidate_route_count": item.diagnostics.get("plan_candidate_route_count", 0),
                    "plan_relaxed_candidate_route_count": item.diagnostics.get(
                        "plan_relaxed_candidate_route_count", 0
                    ),
                    "plan_selected_clearance_mode": item.diagnostics.get(
                        "plan_selected_clearance_mode"
                    ),
                    "plan_rejections": item.diagnostics.get("plan_rejections", ()),
                    "plan_start_metrics": item.diagnostics.get("plan_start_metrics"),
                    "plan_target_metrics": item.diagnostics.get("plan_target_metrics"),
                    "plan_selected_route_score": item.diagnostics.get("plan_selected_route_score"),
                    "plan_selected_route_length": item.diagnostics.get("plan_selected_route_length"),
                    "plan_selected_route_minimum_clearance": item.diagnostics.get(
                        "plan_selected_route_minimum_clearance"
                    ),
                    "route_target_shift": item.diagnostics.get("route_target_shift"),
                    "route_deviation": item.diagnostics.get("route_deviation"),
                    "route_safety_margin": item.diagnostics.get("route_safety_margin", 0),
                    "route_clearance_radius": item.diagnostics.get("route_clearance_radius", 0.0),
                    "route_clearance_weight": item.diagnostics.get("route_clearance_weight", 0.0),
                    "route_dead_end_weight": item.diagnostics.get("route_dead_end_weight", 0.0),
                    "route_minimum_clearance": item.diagnostics.get("route_minimum_clearance", 0.0),
                    "route_footprint_radius": item.diagnostics.get("route_footprint_radius", 0.0),
                    "no_progress_ticks": item.diagnostics.get("no_progress_ticks", 0),
                    "recovery_attempts": item.diagnostics.get("recovery_attempts", 0),
                    "recovery_target": item.diagnostics.get("recovery_target"),
                    "observed_velocity": item.diagnostics.get("observed_velocity", (0.0, 0.0)),
                    "observed_speed": item.diagnostics.get("observed_speed", 0.0),
                    "observed_displacement": item.diagnostics.get("observed_displacement", 0.0),
                    "command_duration_ms": item.diagnostics.get("command_duration_ms", 0),
                    "command_vector": item.diagnostics.get("command_vector", (0.0, 0.0)),
                    "local_controller": item.diagnostics.get("local_controller", {}),
                    "motion_loop_policy": item.diagnostics.get("motion_loop_policy"),
                    "motion_loop_state": item.diagnostics.get("motion_loop_state"),
                    "motion_loop_complexity": item.diagnostics.get("motion_loop_complexity"),
                    "motion_loop_command_id": item.diagnostics.get("motion_loop_command_id"),
                    "calibration_confidence": item.diagnostics.get("calibration_confidence"),
                    "calibration_samples": item.diagnostics.get("calibration_samples"),
                    "calibration_speed_gain": item.diagnostics.get("calibration_speed_gain"),
                    "route_points": len(item.route),
                    "route_end": item.route[-1] if item.route else None,
                    "vector_native": tuple(round(float(value), 4) for value in item.vector),
                    "vector_input": (
                        None if input_vector is None
                        else tuple(round(float(value), 4) for value in input_vector)
                    ),
                }
            self._logger.info(
                "step=follow_experiment.motion count=%s target_native=%s observations=%s",
                self._follow_tick_count,
                runtime.remote.position.position if runtime.remote.position is not None else None,
                motion_details,
            )
            if (
                self._follow_program_output is not None
                and (
                    self._follow_tick_count == 1
                    or self._follow_last_program_diagnostics_at_ms is None
                    or now_ms - self._follow_last_program_diagnostics_at_ms
                    >= self._PROGRAM_DIAGNOSTICS_INTERVAL_MS
                )
            ):
                self._follow_last_program_diagnostics_at_ms = now_ms
                try:
                    self._logger.info(
                        "step=follow_experiment.program_diagnostics count=%s diagnostics=%s",
                        self._follow_tick_count,
                        self._follow_program_output.diagnostics(),
                    )
                except Exception as exc:
                    self._logger.exception(
                        "step=follow_experiment.program_diagnostics_failed error=%s", exc
                    )
        if self._follow_live_mode:
            self._publish_follow_prediction_hints()
        self._render_follow_overlay()
        states = " | ".join(
            f"{role_key}={item.state.value}:{item.reason}" for role_key, item in observations.items()
        )
        target = runtime.remote.position
        target_text = "未设置" if target is None else f"({target.position[0]:.1f},{target.position[1]:.1f})"
        self.follow_status_label.setText(
            f"{'实时跟随' if self._follow_live_mode else '跟随实验'}：目标 {target_text} | {states}"
        )
        self._logger.debug(
            "step=follow_experiment.tick_end attempt=%s tick=%s elapsed_ms=%.3f "
            "outcome=tracking sync_phase=%s live_sync_pending=%s states=%s",
            tick_attempt,
            self._follow_tick_count,
            (time.perf_counter() - tick_started) * 1000.0,
            self._follow_sync_phase,
            live_sync_pending,
            states,
        )

    def _enter_live_follow_sync(self, *, phase: str, now_ms: int, captured_at_ms: int) -> None:
        """Start a bounded visual synchronization barrier for live follow.

        The first command and the first post-command screenshot are not
        synchronous.  Keep the accepted registration frame as a baseline and
        wait for a strictly newer frame before arming the normal prediction
        and innovation gate.  This is deliberately page-local: click-target
        experiments already use their own direct visual update path.
        """
        if phase not in {"cold_start", "recovery_sync"}:
            raise ValueError(f"unsupported live-follow sync phase: {phase}")
        self._follow_sync_phase = phase
        self._follow_sync_started_at_ms = int(now_ms)
        self._follow_sync_baseline_captured_at_ms = int(captured_at_ms)
        self._follow_sync_frame_count = 0
        self._follow_sync_last_log_at_ms = None
        self._logger.info(
            "step=live_role_follow.sync_enter phase=%s started_at_ms=%s "
            "baseline_captured_at_ms=%s",
            phase, now_ms, captured_at_ms,
        )

    def _sync_live_follow_from_fresh_frame(
        self, state: Any, *, captured_at_ms: int, now_ms: int,
    ) -> bool:
        """Promote one fresh, complete dual frame to the live-follow anchor."""
        tracker = self._follow_role_tracker
        runtime = self._follow_runtime
        leader = self._follow_leader_role
        if tracker is None or runtime is None or leader is None:
            return False
        roles = (leader, *self._follow_program_roles)
        role_observations = state.diagnostics.get("role_observations", {})
        points: dict[str, tuple[float, float]] = {}
        for role in roles:
            point = state.players.get(role.actor_id)
            info = role_observations.get(role.actor_id)
            visible = (
                bool(info.get("visible")) if isinstance(info, dict)
                else state.status in {"tracking", "degraded"} and point is not None
            )
            if point is None or not visible:
                self._logger.info(
                    "step=live_role_follow.sync_waiting phase=%s reason=role_not_fresh "
                    "role=%s captured_at_ms=%s",
                    self._follow_sync_phase, role.key, captured_at_ms,
                )
                return False
            points[role.actor_id] = (float(point[0]), float(point[1]))
        for role in roles:
            tracker.seed(
                role.key, runtime.map_identity.map_version,
                points[role.actor_id], captured_at_ms=int(captured_at_ms),
            )
            # The first post-sync command and the next screenshot can still be
            # separated by one or two capture/Host cycles.  Re-arm the bounded
            # phase using the capture clock, which is the clock used by
            # ``CommandRoleTracker.observe`` for its innovation gate.
            tracker.arm_visual_phase(
                role.key,
                started_at_ms=int(captured_at_ms),
                grace_ms=self._follow_visual_phase_grace_ms,
            )
        self._follow_sync_phase = "tracking"
        self._follow_sync_frame_count += 1
        self._follow_rejected_visual = {}
        self._clear_live_follow_recovery_episode("fresh_sync")
        # All live-follow state is keyed by the stable RoleId key.  ``points``
        # is intentionally keyed by actor_id because it is also used to read
        # the frame, but the tick loop indexes this cache with ``role.key``.
        # Keeping the two namespaces separate prevents the continuity gate
        # from silently losing every previous visual point.
        self._follow_last_visual_positions = {
            role.key: points[role.actor_id] for role in roles
        }
        self._follow_last_visual_at_ms = {
            role.key: int(captured_at_ms) for role in roles
        }
        self._follow_last_evaluated_visual_at_ms = {
            role.key: int(captured_at_ms) for role in roles
        }
        self._logger.info(
            "step=live_role_follow.sync_ready phase=%s frame_count=%s "
            "captured_at_ms=%s frame_age_ms=%s positions=%s",
            self._follow_sync_phase,
            self._follow_sync_frame_count,
            captured_at_ms,
            max(0, int(now_ms) - int(captured_at_ms)),
            points,
        )
        return True

    def _request_live_follow_reanchor(self, reason: str) -> None:
        preserve_follow = bool(self._follow_live_mode and self._follow_runtime is not None)
        if preserve_follow and self._follow_recovery_episode_active:
            self._follow_recovery_episode_suppressed += 1
            if self._follow_recovery_episode_suppressed == 1 or (
                self._follow_recovery_episode_suppressed % 25 == 0
            ):
                self._logger.info(
                    "step=live_role_follow.recovery_episode_suppressed reason=%s "
                    "count=%s episode_reason=%s pending=%s",
                    reason,
                    self._follow_recovery_episode_suppressed,
                    self._follow_recovery_episode_reason,
                    self._follow_recovery_pending,
                )
            return
        if preserve_follow:
            self._begin_live_follow_recovery_episode(reason)
        if not self._claim_dual_recovery(reason=f"follow:{reason}"):
            self._logger.warning(
                "step=live_role_follow.reanchor_rejected reason=%s "
                "tick=%s attempts=%s last_observations=%s last_visual_positions=%s",
                reason,
                self._follow_tick_count,
                self._follow_tick_attempt_count,
                self._last_follow_observations,
                self._follow_last_visual_positions,
            )
            if preserve_follow:
                self._follow_recovery_pending = True
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                self.follow_status_label.setText("实时跟随：重定位冷却中，跟随预测继续")
                self._logger.warning(
                    "step=live_role_follow.recovery_deferred reason=cooldown "
                    "follow_prediction_continues=True",
                )
                self._schedule_live_follow_recovery_retry("cooldown")
            else:
                self.stop_dual_motion()
                self.follow_status_label.setText("实时跟随：重定位冷却中，已安全停止输入")
            return
        self._logger.warning(
            "step=live_role_follow.reanchor reason=%s tick=%s attempts=%s "
            "sync_phase=%s rejected_visual=%s occluded=%s observations=%s "
            "last_visual_positions=%s output_snapshot=%s",
            reason,
            self._follow_tick_count,
            self._follow_tick_attempt_count,
            self._follow_sync_phase,
            self._follow_rejected_visual,
            self._follow_occluded_roles,
            self._last_follow_observations,
            self._follow_last_visual_positions,
            None if self._follow_program_output is None else self._follow_program_output.snapshot(),
        )
        self._follow_recovery_pending = preserve_follow
        self._save_dual_follow_recovery_context()
        if self._follow_program_output is not None:
            self._follow_program_output.release_all()
        if preserve_follow:
            self._start_dual_motion(recovery=True, preserve_follow=True)
        else:
            self._start_dual_motion(recovery=True)

    def _schedule_live_follow_recovery_retry(self, reason: str) -> None:
        """Retry visual recovery without terminating the active follow session."""
        if (
            self._closing
            or not self._follow_recovery_pending
            or self._follow_recovery_retry_scheduled
        ):
            return
        self._follow_recovery_retry_scheduled = True
        # Global dual-player registration is expensive. Back off failed
        # attempts instead of starting another computation every second.
        retry_decision = self._recovery_controller.schedule_retry(reason)
        delay_ms = retry_decision.retry_after_ms or self._follow_recovery_retry_delay_ms or 5_000
        delay_ms = min(15_000, max(5_000, int(delay_ms)))
        self._follow_recovery_retry_delay_ms = min(15_000, delay_ms * 2)
        self._logger.info(
            "step=live_role_follow.recovery_retry_scheduled reason=%s "
            "delay_ms=%s next_delay_ms=%s",
            reason, delay_ms, self._follow_recovery_retry_delay_ms,
        )

        def retry() -> None:
            self._follow_recovery_retry_scheduled = False
            if (
                self._closing
                or not self._follow_recovery_pending
                or self._follow_runtime is None
            ):
                return
            self._start_dual_motion(recovery=True, preserve_follow=True)

        QTimer.singleShot(delay_ms, retry)

    def _claim_dual_recovery(self, *, reason: str) -> bool:
        """Claim the single page-level recovery budget for one re-anchor."""
        now_ms = int(time.time() * 1000)
        last_ms = self._dual_last_recovery_at_ms
        if (
            last_ms is not None
            and now_ms - int(last_ms) < self._DUAL_RECOVERY_COOLDOWN_MS
        ):
            self._logger.warning(
                "step=dual_motion.recovery_cooldown reason=%s elapsed_ms=%s cooldown_ms=%s",
                reason,
                max(0, now_ms - int(last_ms)),
                self._DUAL_RECOVERY_COOLDOWN_MS,
            )
            return False
        self._dual_last_recovery_at_ms = now_ms
        self._logger.info(
            "step=dual_motion.recovery_claimed reason=%s cooldown_ms=%s",
            reason,
            self._DUAL_RECOVERY_COOLDOWN_MS,
        )
        return True

    def _render_follow_overlay(self) -> None:
        runtime = self._follow_runtime
        source_size = self._dual_map_source_size
        transform = self._dual_map_transform
        state = self._latest_dual_state
        observations = self._last_follow_observations
        if runtime is None or source_size is None or transform is None or state is None:
            return
        display_players = {
            str(identity): localization_display_point(
                point, source_size=source_size, transform=transform,
            )
            for identity, point in state.players.items() if point is not None
        }
        if self._follow_live_mode and observations:
            display_players = {
                observation.follower.actor_id: localization_display_point(
                    observation.position, source_size=source_size, transform=transform,
                )
                for observation in observations.values() if observation.position is not None
            }
        simulated_positions = []
        routes = {}
        for role_key, observation in observations.items():
            actual = state.players.get(observation.follower.actor_id)
            if self._follow_live_mode and observation.follower.actor_id in self._follow_occluded_roles:
                if observation.position is not None:
                    simulated_positions.append(localization_display_point(
                        observation.position, source_size=source_size, transform=transform,
                    ))
            if (
                runtime.mode_for(observation.follower) is ControlMode.SIMULATED
                and observation.position is not None
                and actual is not None
                and (abs(observation.position[0] - actual[0]) > 0.5
                     or abs(observation.position[1] - actual[1]) > 0.5)
            ):
                simulated_positions.append(localization_display_point(
                    observation.position, source_size=source_size, transform=transform,
                ))
            route_points = []
            if observation.position is not None:
                route_points.append(observation.position)
            route_points.extend(observation.route)
            if observation.target_position is not None and (
                not route_points
                or point_distance(route_points[-1], observation.target_position) > 1e-6
            ):
                route_points.append(observation.target_position)
            if len(route_points) >= 2:
                routes[role_key] = tuple(
                    localization_display_point(point, source_size=source_size, transform=transform)
                    for point in route_points
                )
        target = runtime.remote.position
        runtime_target_display = (
            localization_display_point(target.position, source_size=source_size, transform=transform)
            if target is not None else None
        )
        # Prefer the page-level click marker.  It is updated before the
        # runtime receives the click, so the user sees the exact destination
        # immediately and it remains stable while the runtime replans.
        target_display = (
            runtime_target_display if self._follow_live_mode
            else self._clicked_target_display or runtime_target_display
        )
        self.map_widget.set_overlay(
            players=display_players, candidates=simulated_positions,
            target=target_display, routes=routes,
        )

    def _render_dual_first_frame_result(self, result: Any, snapshot: Any, *, render_map: bool = True) -> None:
        diagnostics = dict(getattr(result, "diagnostics", {}) or {})
        read_count = self._dual_first_frame_read_count
        details = [
            f"双人首帧：{result.status} | {result.reason} | 内存读取 {read_count} 次",
            f"候选 {diagnostics.get('candidate_count', 0)} | 配对 {diagnostics.get('evaluated_assignment_count', 0)}",
        ]
        for identity, player in getattr(result, "players", {}).items():
            details.append(
                f"{identity}: screen=({player.screen_position[0]:.1f}, {player.screen_position[1]:.1f}) "
                f"map=({player.mapped_position[0]:.1f}, {player.mapped_position[1]:.1f}) "
                f"误差 {player.anchor_error:.2f} | 置信度 {player.confidence:.3f}"
            )
        registration = getattr(result, "primary_registration", None)
        transform = getattr(registration, "transform", None)
        if transform is not None:
            details.append(
                f"方向 {transform.angle_degrees:.1f}°"
                f"{'，水平镜像' if transform.reflect_horizontal else ''} | 比例 {transform.scale:.3f}"
            )
        registration_diagnostics = dict(getattr(registration, "diagnostics", {}) or {})
        if registration_diagnostics:
            joint = diagnostics.get("joint_initialization", {})
            details.append(
                f"共同墙体覆盖率 {float(registration_diagnostics.get('joint_shape_coverage', registration_diagnostics.get('best_forward_coverage', 0.0))):.3f}"
                f" | 配对误差 {float(joint.get('registration_pair_distance_error', 0.0)):.2f}"
            )
            if joint:
                details.append(
                    f"配对模式 {joint.get('pair_mode', 'unknown')}"
                    f" | 屏幕基线 {float(joint.get('screen_baseline', 0.0)):.2f}"
                    f" | 网格基线 {float(joint.get('native_baseline', 0.0)):.2f}"
                )
        self.dual_first_frame_status_label.setText("\n".join(details))
        if not render_map:
            return
        base = terrain_pixmap(snapshot, self._map_orientation())
        transform = getattr(registration, "transform", None)
        overlay = prepare_localization_map(base, transform)
        source_size = (base.width(), base.height())
        for player in getattr(result, "players", {}).values():
            display_point = localization_display_point(
                player.mapped_position,
                source_size=source_size,
                transform=transform,
            )
            overlay = present_player_position_overlay(
                overlay,
                cast("PlayerPositionSample", SimpleNamespace(grid=display_point)),
                source_shape=(overlay.height(), overlay.width()),
                orientation=None,
            )
        self.map_widget.set_image(overlay)
        players = tuple(getattr(result, "players", {}).values())
        if players:
            self.map_widget.focus_on_point(
                localization_display_point(
                    players[0].mapped_position,
                    source_size=source_size,
                    transform=transform,
                ),
                zoom_multiplier=self.map_follow_zoom_multiplier,
            )

    def start_hybrid_localization(self) -> None:
        if self._snapshot is None:
            self._show_error(RuntimeError("请先获取当前地图"))
            return
        if self.hybrid_localization_factory is None:
            self._show_error(RuntimeError("混合定位实验工厂未注入"))
            return
        self.stop_dual_motion()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        self.stop_preview()
        self._dual_preview_active = False
        if self.capture_monitor_window is not None:
            stop_monitoring = getattr(self.capture_monitor_window, "stop_monitoring", None)
            if callable(stop_monitoring):
                stop_monitoring()
        try:
            experiment = self.hybrid_localization_factory(
                self._snapshot,
                lambda: self.monitor_config,
            )
            experiment.session.add_listener(self.handle_hybrid_state)
            experiment.session.start()
            self._hybrid_experiment = experiment
            self.hybrid_timer.setInterval(self._localization_interval())
            self.hybrid_timer.start()
            self._tick_hybrid_localization()
        except Exception as exc:
            self.hybrid_timer.stop()
            self._hybrid_experiment = None
            self._logger.exception("step=hybrid.start_failed error=%s", exc)
            self._show_error(exc)
            return
        self.start_hybrid_button.setEnabled(False)
        self.stop_hybrid_button.setEnabled(True)
        self.start_single_frame_button.setEnabled(False)
        self.stop_single_frame_button.setEnabled(True)
        self._logger.info("step=hybrid.started interval_ms=%s", self.hybrid_timer.interval())

    def start_multiframe_localization(self) -> None:
        if self._snapshot is None or self.multiframe_localization_factory is None:
            self._show_error(RuntimeError("请先获取地图并注入多帧实验工厂"))
            return
        binding = getattr(self.monitor_config, "binding", None)
        if binding is None:
            self._show_error(RuntimeError("请先配置 PoE2 小地图监控区域"))
            self._logger.warning("step=multiframe.start_rejected reason=missing_monitor_binding")
            return
        self.stop_dual_motion()
        self.stop_multiframe_localization()
        # The preview and detached monitor use the same capture/recognizer
        # resources.  Keep one sampling loop active for deterministic timing.
        self.stop_preview()
        self._dual_preview_active = False
        if self.capture_monitor_window is not None:
            stop_monitoring = getattr(self.capture_monitor_window, "stop_monitoring", None)
            if callable(stop_monitoring):
                stop_monitoring()
        experiment = None
        try:
            experiment = self.multiframe_localization_factory(self._snapshot, lambda: self.monitor_config)
            strategy_a, strategy_b = self.multiframe_panel.selected_strategies()
            experiment.coordinator.set_strategies_enabled(strategy_a=strategy_a, strategy_b=strategy_b)
            experiment.session.start()
            self._multiframe_experiment = experiment
            self._multiframe_trajectory.clear()
            self._multiframe_trajectory_version = 0
            self._multiframe_timer.setInterval(self._localization_interval())
            self._multiframe_timer.start()
            self._tick_multiframe()
        except Exception as exc:
            self._multiframe_timer.stop()
            if experiment is not None:
                close = getattr(experiment.session, "close", None)
                if callable(close):
                    close()
            self._multiframe_experiment = None
            self.multiframe_panel.set_running(False)
            self.multiframe_panel.set_archive_available(False)
            self._logger.exception("step=multiframe.start_failed error=%s", exc)
            self._show_error(exc)
            return
        self.start_multiframe_button.setEnabled(False)
        self.stop_multiframe_button.setEnabled(True)
        self.multiframe_panel.set_running(True)
        self.multiframe_panel.set_archive_available(False)
        self._logger.info("step=multiframe.started interval_ms=%s", self._multiframe_timer.interval())

    def stop_multiframe_localization(self) -> None:
        self._multiframe_timer.stop()
        experiment = self._multiframe_experiment
        if experiment is not None:
            close = getattr(experiment.session, "close", None)
            if callable(close):
                close()
            else:
                experiment.session.stop()
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory.clear()
        self._multiframe_trajectory_version = 0
        self.start_multiframe_button.setEnabled(self.multiframe_localization_factory is not None and self._snapshot is not None)
        self.stop_multiframe_button.setEnabled(False)
        self.multiframe_panel.set_running(False)
        self.multiframe_panel.set_archive_available(False)

    def reset_multiframe_localization(self) -> None:
        self.stop_multiframe_localization()
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory.clear()
        self._multiframe_trajectory_version = 0
        self.multiframe_status_label.setText("多帧定位：未启动")
        self.multiframe_position_label.setText("多帧位置：暂无")
        self.multiframe_panel.set_submap(None)
        self.multiframe_panel.set_archive_available(False)

    def save_multiframe_experiment(self) -> None:
        experiment = self._multiframe_experiment
        if experiment is None:
            self._show_error(RuntimeError("多帧定位实验尚未启动"))
            return
        if not self._multiframe_archive_ready():
            self._show_error(RuntimeError("多帧实验尚未形成可归档的锚点、参考地图和证据"))
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        target = Path("data/poe2_live_terrain_test/multiframe_sessions") / timestamp
        try:
            saved = experiment.archive.save(
                target,
                evidence=experiment.window.snapshot(),
                anchor=experiment.coordinator.anchor,
                instance_id=experiment.coordinator.instance_id,
                reference=experiment.coordinator.reference,
                estimate=self._last_multiframe_state,
                diagnostics={
                    "recovery_revision": experiment.coordinator.recovery_revision,
                    "memory_read_count": int(getattr(experiment.anchor_provider, "read_count", 0)),
                    "phase": experiment.coordinator.phase.value,
                },
            )
        except Exception as exc:
            self._logger.exception("step=multiframe.archive_failed error=%s", exc)
            self._show_error(exc)
            return
        self._logger.info("step=multiframe.archive_saved path=%s", saved)
        self.multiframe_status_label.setText(f"多帧实验已保存：{saved}")

    def _multiframe_archive_ready(self) -> bool:
        experiment = self._multiframe_experiment
        if experiment is None:
            return False
        coordinator = getattr(experiment, "coordinator", None)
        window = getattr(experiment, "window", None)
        return bool(
            getattr(coordinator, "anchor", None) is not None
            and getattr(coordinator, "reference", None) is not None
            and window is not None
            and tuple(window.snapshot())
        )

    def _tick_multiframe(self) -> None:
        experiment = self._multiframe_experiment
        if experiment is None:
            return
        try:
            state = experiment.session.tick()
        except Exception as exc:
            self._logger.exception("step=multiframe.tick_failed error=%s", exc)
            self.stop_multiframe_localization()
            self._show_error(exc)
            return
        self._last_multiframe_state = state
        candidates = tuple(getattr(state, "candidate_regions", ()) or ())
        keyframes = len(experiment.window.snapshot())
        reads = int(getattr(experiment.anchor_provider, "read_count", 0))
        evidence_bytes = int(getattr(experiment.window, "estimated_bytes", 0))
        registration_version = int(getattr(state, "registration_version", 0))
        if registration_version != self._multiframe_trajectory_version:
            self._multiframe_trajectory.clear()
            self._multiframe_trajectory_version = registration_version
        if state.position is not None and state.fresh:
            self._multiframe_trajectory.append(tuple(state.position))
            self._multiframe_trajectory = self._multiframe_trajectory[-200:]
        self.multiframe_status_label.setText(
            f"多帧定位：{state.status} | evidence {state.evidence_version} | "
            f"候选 {len(candidates)} | 关键帧 {keyframes} | 内存读取 {reads} | "
            f"恢复版本 {experiment.coordinator.recovery_revision} | {state.reason}"
        )
        self.multiframe_position_label.setText(f"多帧位置：{state.position if state.position is not None else '暂无'}")
        self.multiframe_panel.set_state(
            status=state.status,
            evidence_version=state.evidence_version,
            recovery_revision=experiment.coordinator.recovery_revision,
            reason=state.reason,
            position=state.position,
            keyframes=keyframes,
            candidates=len(candidates),
            memory_reads=reads,
            registration_pending=experiment.session.registration_pending,
            strategy_a_status=getattr(experiment.coordinator.last_strategy_a_result, "status", None),
            best_candidate=getattr(experiment.coordinator.last_strategy_b_result, "best", None),
            evidence_bytes=evidence_bytes,
            tick_elapsed_ms=float(getattr(experiment.session, "last_tick_elapsed_ms", 0.0)),
            registration_elapsed_ms=float(getattr(experiment.session, "last_registration_elapsed_ms", 0.0)),
        )
        submap = experiment.submap.rebuild(experiment.window.snapshot())
        self.multiframe_panel.set_submap(submap.wall_mask)
        self.multiframe_panel.set_archive_available(self._multiframe_archive_ready())
        if self._snapshot is not None:
            native_pixmap = terrain_pixmap(self._snapshot)
            overlay_state = build_localization_presentation(
                state,
                registration=experiment.coordinator.registration,
                coordinator_registration_version=int(
                    getattr(experiment.coordinator, "registration_version", registration_version)
                ),
                trajectory=self._multiframe_trajectory,
                candidates=candidates,
            )
            overlay = present_localization_overlay(native_pixmap, overlay_state)
            self.map_widget.set_image(overlay)
            self._focus_map_on_state(overlay_state, source_size=native_pixmap.size())
            transform = getattr(experiment.coordinator.registration, "transform", None)
            lines = [line for line in self.metadata_label.text().splitlines() if not line.startswith("方向：")]
            if transform is not None and overlay_state.registration is not None:
                lines.append(
                    f"方向：多帧自动校准 {float(transform.angle_degrees):.1f}°"
                    f"{'，水平镜像' if transform.reflect_horizontal else ''}"
                )
            else:
                lines.append("方向：等待自动校准（native）")
            self.metadata_label.setText("\n".join(lines))
        self._logger.info(
            "step=multiframe.state phase=%s status=%s source=%s position=%s evidence=%s keyframes=%s evidence_bytes=%s candidates=%s reads=%s pending=%s tick_ms=%.2f registration_ms=%.2f reason=%s diagnostics=%s",
            experiment.coordinator.phase.value,
            state.status,
            state.source,
            state.position,
            state.evidence_version,
            keyframes,
            evidence_bytes,
            len(candidates),
            reads,
            experiment.session.registration_pending,
            float(getattr(experiment.session, "last_tick_elapsed_ms", 0.0)),
            float(getattr(experiment.session, "last_registration_elapsed_ms", 0.0)),
            state.reason,
            dict(getattr(state, "diagnostics", {}) or {}),
        )

    def stop_hybrid_localization(self) -> None:
        self.hybrid_timer.stop()
        experiment = self._hybrid_experiment
        if experiment is not None:
            experiment.session.stop()
        self.start_hybrid_button.setEnabled(
            self.hybrid_localization_factory is not None and self._snapshot is not None
        )
        self.stop_hybrid_button.setEnabled(False)
        self.retry_hybrid_button.setEnabled(False)
        self.stop_single_frame_button.setEnabled(False)
        self.start_single_frame_button.setEnabled(
            self.hybrid_localization_factory is not None and self._snapshot is not None
        )

    def retry_hybrid_recovery(self) -> None:
        if self._hybrid_experiment is None:
            self._show_error(RuntimeError("混合定位尚未启动"))
            return
        try:
            self._hybrid_experiment.session.retry_recovery()
        except Exception as exc:
            self._logger.exception("step=hybrid.retry_failed error=%s", exc)
            self._show_error(exc)
            return
        self.retry_hybrid_button.setEnabled(False)
        self.hybrid_status_label.setText("混合定位：已允许单次恢复，等待下一帧")
        self._logger.info("step=hybrid.retry_requested")

    def _tick_hybrid_localization(self) -> None:
        if self._hybrid_experiment is None:
            return
        try:
            self._hybrid_experiment.session.tick()
        except Exception as exc:
            self.hybrid_timer.stop()
            self.stop_hybrid_button.setEnabled(False)
            self.start_hybrid_button.setEnabled(self._snapshot is not None)
            self._logger.exception("step=hybrid.tick_failed error=%s", exc)
            self._show_error(exc)

    def _hybrid_read_count(self) -> int:
        provider = getattr(self._hybrid_experiment, "anchor_provider", None)
        return int(getattr(provider, "read_count", 0))

    def _map_orientation(self) -> TerrainOrientation:
        return TerrainOrientation()

    def handle_hybrid_state(self, state: Any) -> None:
        self._last_hybrid_state = state
        mode = getattr(getattr(state, "mode", "unknown"), "value", getattr(state, "mode", "unknown"))
        source = str(getattr(state, "source", "failed"))
        confidence = float(getattr(state, "confidence", 0.0))
        revision = int(getattr(state, "recovery_revision", 0))
        reason = str(getattr(state, "reason", "") or "")
        reads = self._hybrid_read_count()
        details = (
            f"混合定位：{mode} | 来源 {source} | 置信度 {confidence:.3f} | "
            f"内存读取 {reads} 次 | 恢复版本 {revision}"
        )
        if reason:
            details += f" | {reason}"
        diagnostics = getattr(state, "diagnostics", {})
        if isinstance(diagnostics, Mapping):
            registration_reason = str(diagnostics.get("reason", "") or "")
            if registration_reason and registration_reason != reason:
                details += f" | {registration_reason}"
            numeric_details = (
                ("best_score", "候选分", 3),
                ("best_forward_coverage", "覆盖", 3),
                ("best_angle", "角度", 1),
                ("best_scale", "比例", 3),
                ("best_anchor_error", "锚点误差", 2),
            )
            for key, label, precision in numeric_details:
                value = diagnostics.get(key)
                if isinstance(value, (int, float)):
                    suffix = "°" if key == "best_angle" else ""
                    details += f" | {label} {float(value):.{precision}f}{suffix}"
        self.hybrid_status_label.setText(details)
        self.single_frame_status_label.setText(details.replace("混合定位：", "首帧定位：", 1))
        position = getattr(state, "position", None)
        if position is None:
            self.hybrid_position_label.setText("实时位置：本帧无可信位置")
        else:
            self.hybrid_position_label.setText(
                f"实时位置：({float(position[0]):.2f}, {float(position[1]):.2f})"
            )
        mode_name = str(mode)
        self.retry_hybrid_button.setEnabled(mode_name == "recovery_required")
        if self._terrain_base_pixmap is not None:
            base_pixmap = self._terrain_base_pixmap
            overlay = present_localization_overlay(base_pixmap, state)
            self.map_widget.set_image(overlay)
            self._focus_map_on_state(state, source_size=base_pixmap.size())
        transform = getattr(getattr(state, "registration", None), "transform", None)
        if transform is not None:
            lines = [
                line for line in self.metadata_label.text().splitlines()
                if not line.startswith("方向：")
            ]
            lines.append(
                f"方向：自动校准 {float(transform.angle_degrees):.1f}°"
                f"{'，水平镜像' if transform.reflect_horizontal else ''}"
            )
            self.metadata_label.setText("\n".join(lines))
        if self.capture_monitor_window is not None:
            self.capture_monitor_window.handle_hybrid_state(state, read_count=reads)
        self._logger.info(
            "step=hybrid.state mode=%s source=%s confidence=%.3f position=%s reads=%s revision=%s reason=%s diagnostics=%s",
            mode,
            source,
            confidence,
            position,
            reads,
            revision,
            reason,
            dict(diagnostics) if isinstance(diagnostics, Mapping) else {},
        )

    def _focus_map_on_state(self, state: Any, *, source_size) -> None:
        position = getattr(state, "position", None)
        if position is None:
            position = getattr(state, "latest_confirmed_position", None)
        if position is None:
            return
        registration = getattr(state, "registration", None)
        transform = getattr(registration, "transform", None)
        point = localization_display_point(
            position,
            source_size=(source_size.width(), source_size.height()),
            transform=transform,
        )
        self.map_widget.focus_on_point(
            point,
            zoom_multiplier=self.map_follow_zoom_multiplier,
        )

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

    def _show_error(self, error: Exception) -> None:
        self.status_label.setText("状态：错误")
        self.error_label.setText(f"错误：{error}")

    def shutdown(self) -> None:
        self._closing = True
        self._invalidate_dual_motion_session()
        self.stop_program_move_probe()
        self.stop_dual_motion()
        self.stop_preview()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        if self.capture_monitor_window is not None:
            self.capture_monitor_window.close()
        self.localization_control_dialog.close()
        if getattr(self, "_log_handler", None) is not None:
            self._logger.removeHandler(self._log_handler)
            self._log_handler.deleteLater()
        self.service.reset()


__all__ = ["Poe2CaptureTestPage"]

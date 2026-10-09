"""PoE2 capture-only test page used to inspect live evidence and terrain data."""

from __future__ import annotations

import math
import time
import logging
import inspect
from concurrent.futures import Future, ThreadPoolExecutor
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
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
from shiboken6 import isValid as _qt_is_valid

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
    FollowObservation,
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
from auto_modules.features.poe2.live_terrain.experimental.follow_contract import DYNAMIC_FOLLOW_CONTRACT
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.recovery_coordinator import (
    RecoveryCoordinator,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.global_reanchor import (
    GlobalReanchorBackend,
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
from auto_modules.features.poe2.live_terrain.experimental.application import (
    ExperimentRuntime,
)
from auto_modules.features.poe2.live_terrain.experimental.follow_engine.engine import (
    FollowEngineStart,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer import (
    DualMotionController,
)
from auto_modules.features.poe2.live_terrain.experimental.follow.target_sources import (
    MutableTargetSource,
)
from auto_modules.features.poe2.live_terrain.experimental.composition import (
    build_experiment_composition,
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
from .localization_mixin import Poe2LocalizationMixin
from .page_lifecycle_mixin import Poe2PageLifecycleMixin
from .probe_mixin import Poe2ProbeMixin
from .dual_motion_mixin import Poe2DualMotionMixin
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
from .follow_engine_adapter import Poe2FollowEnginePageAdapter

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
            # The feature logger outlives individual experiment pages.  A
            # worker can finish while Qt is tearing down the page, so never
            # emit into a deleted QObject or its queued widget slot.
            if not _qt_is_valid(self):
                return
            parent = self.parent()
            if parent is not None and not _qt_is_valid(parent):
                return
            self.message_emitted.emit(self.format(record))
        except Exception:
            self.handleError(record)


class Poe2CaptureTestPage(Poe2LocalizationMixin, Poe2PageLifecycleMixin, Poe2ProbeMixin, Poe2DualMotionMixin, QWidget):
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
    _FOLLOW_COMMAND_ARM_DELAY_MS = 10_000
    _FOLLOW_COMMAND_ARM_LOG_INTERVAL_MS = 1_000
    _follow_lifecycle_finished = Signal(int, str, bool, object)

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
        follow_engine_page_adapter: Poe2FollowEnginePageAdapter | None = None,
        follow_engine_page_adapter_factory: Callable[..., Any] | None = None,
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
        # The modular engine is opt-in until its real capture/memory/Host
        # composition is injected and accepted.  Keeping the adapter at the
        # page boundary makes the migration reversible and prevents the old
        # runtime and the new port from owning a controller simultaneously.
        self._follow_engine_page_adapter = follow_engine_page_adapter
        self._follow_engine_page_adapter_factory = follow_engine_page_adapter_factory
        self._follow_engine_composition = None
        self._follow_engine_adapter_owned = False
        self._modular_follow_active = False
        self._modular_follow_live_mode = False
        self.open_config_callback = open_config
        self.capture_monitor_window = None
        self._logger = get_terrain_logger()
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(self._preview_interval())
        self.preview_timer.timeout.connect(self._on_preview_timer)
        self.hybrid_timer = QTimer(self)
        self.hybrid_timer.setInterval(self._localization_interval())
        self.hybrid_timer.timeout.connect(self._on_hybrid_timer)
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
        # Recovery is an edge event, but the latest-only worker may overwrite
        # the frame that carried ``recovery_requested=True``.  Keep the last
        # revision consumed by this tracker generation so a persistent
        # ``recovery_required`` state can safely re-emit the edge once.
        self._dual_last_handled_recovery_revision = 0
        self._dual_motion_controller = DualMotionController()
        self._dual_last_ui_render_at = 0.0
        self._dual_last_overlay_render_at = 0.0
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
        self._click_target_source = MutableTargetSource()
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
        # Tests may set this to zero; production keeps the ten-second focus
        # handoff window requested for the real game workflow.
        self._follow_command_arm_delay_ms = self._FOLLOW_COMMAND_ARM_DELAY_MS
        self._follow_output_not_before_ms: int | None = None
        self._follow_output_delay_last_log_at_ms: int | None = None
        # Per-control-tick profiling is intentionally kept separate from the
        # functional state.  It is finalized even when a tick returns early,
        # so a stalled/recovery path is measurable rather than invisible.
        self._follow_tick_timing: dict[str, float] | None = None
        self._follow_tick_timing_sequence = 0
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
        # Live follow uses the new frame-first recovery policy.  The legacy
        # RecoveryController remains available for static/legacy experiments
        # but must not schedule live-follow retries.
        self._live_recovery_policy = RecoveryCoordinator()
        self._live_memory_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="poe2-live-memory-reanchor"
        )
        # Process.start/join and Host cleanup are lifecycle operations, not UI
        # work.  A single serialized executor prevents overlapping generations
        # while keeping the Qt event loop responsive.
        self._follow_lifecycle_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="poe2-follow-lifecycle"
        )
        self._follow_lifecycle_serial = 0
        self._follow_lifecycle_future: Future[Any] | None = None
        self._modular_follow_start_pending = False
        self._modular_follow_stop_pending = False
        self._modular_follow_restart_requested = False
        self._follow_lifecycle_finished.connect(self._on_follow_lifecycle_finished)
        self._live_memory_future: Future[Any] | None = None
        self._live_memory_started_at_ms: int | None = None
        self._live_global_reanchor = GlobalReanchorBackend(
            lambda **kwargs: self._start_dual_motion(**kwargs)
        )
        self._recovery_controller = RecoveryController()
        self._experiment_runtime = ExperimentRuntime()
        self._experiment_composition = build_experiment_composition()
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
        self._program_probe_arm_timer.timeout.connect(self._on_program_probe_arm_timer)
        self._program_probe_timer = QTimer(self)
        self._program_probe_timer.setInterval(50)
        self._program_probe_timer.timeout.connect(self._on_program_probe_timer)
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(100)
        self._follow_timer.timeout.connect(self._on_follow_timer)
        self._follow_timer_default_interval = self._follow_timer.interval()
        self._dual_target_timer = QTimer(self)
        self._dual_target_timer.setInterval(100)
        self._dual_target_timer.timeout.connect(self._on_dual_target_timer)
        self._dual_motion_timer = QTimer(self)
        self._dual_motion_timer.setInterval(self._localization_interval())
        self._dual_motion_timer.timeout.connect(self._on_dual_motion_timer)
        self._multiframe_experiment = None
        self._last_multiframe_state = None
        self._multiframe_trajectory: list[tuple[float, float]] = []
        self._multiframe_trajectory_version = 0
        self._multiframe_timer = QTimer(self)
        self._multiframe_timer.setInterval(self._localization_interval())
        self._multiframe_timer.timeout.connect(self._on_multiframe_timer)
        self.localization_control_dialog = Poe2LocalizationControlDialog(self)
        self.multiframe_panel = self.localization_control_dialog.panel
        self._build_ui()
        self._log_handler = _UiLogHandler(self)
        self._log_handler.message_emitted.connect(self._append_session_log)
        self._logger.addHandler(self._log_handler)
        self._append_session_log("PoE2 实验会话已创建")
        self._render_state("未初始化")

    def _top_level_hidden_timer_guard(self) -> bool:
        """Suspend orphaned top-level pages when a Qt timer fires.

        Normal application pages are children of ``Poe2LiveTerrainPage`` and
        are suspended by its hide event.  A standalone page (for example an
        experiment harness or an embed that was never shown) has no parent
        lifecycle owner; allowing its timers to run indefinitely can keep
        virtual-gamepad tests and other Qt pages busy.  Direct/manual tick
        calls intentionally bypass this guard.
        """
        if self._closing or self.parent() is not None or self.isVisible():
            return False
        self.suspend()
        return True

    def _on_program_probe_timer(self) -> None:
        if not self._top_level_hidden_timer_guard():
            self._tick_program_move_probe()

    def _on_program_probe_arm_timer(self) -> None:
        if not self._top_level_hidden_timer_guard():
            self._arm_program_move_probe()

    def _on_preview_timer(self) -> None:
        if not self._top_level_hidden_timer_guard():
            self.refresh_preview()

    def _on_hybrid_timer(self) -> None:
        if not self._top_level_hidden_timer_guard():
            self._tick_hybrid_localization()

    def _on_follow_timer(self) -> None:
        if not self._top_level_hidden_timer_guard():
            if self._modular_follow_active:
                self._poll_modular_follow_engine()
            else:
                self._tick_follow_experiment()

    def _on_dual_target_timer(self) -> None:
        if not self._top_level_hidden_timer_guard():
            self._tick_dual_target_experiment()

    def _on_dual_motion_timer(self) -> None:
        if not self._top_level_hidden_timer_guard():
            self._tick_dual_motion()

    def _on_multiframe_timer(self) -> None:
        if not self._top_level_hidden_timer_guard():
            self._tick_multiframe()

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
        self.copy_log_button = QPushButton("复制日志")
        self.copy_log_button.setToolTip("复制当前跟随实验的全部日志，可直接发送排查")
        self.copy_log_button.clicked.connect(self._copy_session_log)
        log_header.addWidget(self.copy_log_button)
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
        compute_started = time.perf_counter()
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
        memory_started = time.perf_counter()
        anchors = experiment.read_anchors(snapshot.metadata.instance_id)
        memory_ms = (time.perf_counter() - memory_started) * 1000.0
        self._logger.info(
            "step=dual_first_frame.memory_success read_count=%s identities=%s anchors=%s",
            anchor_provider.read_count, tuple(anchors),
            {identity: anchor.position for identity, anchor in anchors.items()},
        )
        configured_profiles = getattr(self.monitor_config, "dual_marker_profiles", ())
        profiles = tuple(MarkerColorProfile.from_dict(item) for item in configured_profiles)
        captured_frames = []
        # The first-frame contract is a single snapshot.  The player is
        # stationary during registration; repeated captures only multiply the
        # expensive dual assignment/shape search and block the GUI when this
        # method is invoked from the manual experiment button.
        capture_attempts = 1
        for attempt in range(1, capture_attempts + 1):
            capture_started = time.perf_counter()
            candidate_frame = preview_provider(self.monitor_config)
            capture_ms = (time.perf_counter() - capture_started) * 1000.0
            if candidate_frame is None:
                self._logger.warning(
                    "step=dual_first_frame.capture_empty attempt=%s/%s",
                    attempt, capture_attempts,
                )
            else:
                recognition_started = time.perf_counter()
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
                recognition_ms = (time.perf_counter() - recognition_started) * 1000.0
                captured_frames.append({
                    "raw": candidate_frame,
                    "combined": candidate_combined,
                    "mask": candidate_mask,
                    "observation": candidate_observation,
                    "captured_at_ms": candidate_captured_at_ms,
                })
                self._logger.info(
                    "step=dual_first_frame.capture_success attempt=%s/%s shape=%s capture_ms=%.3f recognition_ms=%.3f",
                    attempt, capture_attempts, getattr(candidate_frame, "shape", None),
                    capture_ms, recognition_ms,
                )
                self._logger.info(
                    "step=dual_first_frame.observation attempt=%s/%s candidates=%s positions=%s",
                    attempt, capture_attempts, len(candidate_observation.candidates),
                    [candidate.local_position for candidate in candidate_observation.candidates],
                )
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
            registration_started = time.perf_counter()
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
            registration_ms = (time.perf_counter() - registration_started) * 1000.0
            diagnostics = dict(getattr(candidate_result, "diagnostics", {}) or {})
            registrations.append((candidate_result, captured, frame, diagnostics))
            self._logger.info(
                "step=dual_first_frame.candidate_result attempt=%s status=%s score=%s "
                "pair_confidence=%s shape_quality=%s registration_ms=%.3f",
                len(registrations), getattr(candidate_result, "status", None),
                diagnostics.get("best_pair_confidence", diagnostics.get("best_score")),
                diagnostics.get("best_pair_confidence"),
                diagnostics.get("best_shape_quality", diagnostics.get("best_forward_coverage")),
                registration_ms,
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
            "step=dual_first_frame.consensus_selected candidates=%s selected_attempt=%s status=%s memory_ms=%.3f total_ms=%.3f",
            len(registrations), int(frame.diagnostics.get("capture_attempt", 0)),
            getattr(result, "status", None),
            memory_ms, (time.perf_counter() - compute_started) * 1000.0,
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
        """Run one dual registration for the manual lab button.

        Production monitor configurations use the same one-shot worker as
        recovery so the expensive registration never blocks the Qt event
        loop. Minimal test configurations without a localization cadence keep
        the synchronous hook for deterministic unit tests.
        """
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
        if hasattr(self.monitor_config, "localization_fps") and self._start_dual_first_frame_async(
            recovery=False,
        ):
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
        phase = "恢复定位" if recovery else "首帧定位"
        self.dual_first_frame_status_label.setText(f"双人首帧：后台{phase}中")
        self.dual_motion_status_label.setText(
            f"双人实时：后台{phase}中，界面保持响应"
        )
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
            else:
                self.dual_first_frame_button.setEnabled(True)
                self.start_dual_motion_button.setEnabled(bool(bundle.result.accepted))
                self.stop_dual_motion_button.setEnabled(False)
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
            self.dual_first_frame_button.setEnabled(self._snapshot is not None)
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
        if (
            _qt_is_valid(self)
            and hasattr(self, "session_log")
            and _qt_is_valid(self.session_log)
        ):
            self.session_log.appendPlainText(str(message))

    def _copy_session_log(self) -> None:
        """Copy the bounded UI log without requiring users to inspect files."""
        if not hasattr(self, "session_log") or not _qt_is_valid(self.session_log):
            return
        text = self.session_log.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
            self._logger.info("step=follow_engine.ui_log_copied chars=%s lines=%s", len(text), text.count("\n") + (1 if text else 0))

    def closeEvent(self, event) -> None:
        """Make widget destruction follow the same cleanup contract as shutdown."""
        self.shutdown()
        super().closeEvent(event)

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

    def _make_follow_runtime(
        self, reference: Any, map_identity: MapIdentity, *, live_role_follow: bool = False,
    ) -> SimulatedFollowRuntime:
        motion = DYNAMIC_FOLLOW_CONTRACT
        arrival_radius = motion.arrival_radius
        return SimulatedFollowRuntime(
            wall_map=reference.wall_layer,
            map_identity=map_identity,
            arrival_radius=arrival_radius,
            resume_radius=motion.resume_radius if live_role_follow else None,
            speed_units_per_second=motion.speed_units_per_second,
            position_ttl_ms=self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            downsample_factor=motion.downsample_factor,
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
            local_lookahead=motion.local_lookahead,
            prediction_horizon=motion.prediction_horizon,
            closed_loop_controller=ClosedLoopMotionController(
                expected_speed=motion.speed_units_per_second,
                arrival_radius=arrival_radius,
                max_frame_age_ms=self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS,
            ),
            continuous_follow=live_role_follow,
        )

    def _modular_follow_target_roles(self) -> tuple[str, ...]:
        """Return roles that should receive a target in the modular engine.

        The page still owns role selection policy.  The engine only receives
        normalized role ids and never needs to know what P1/P2 means.
        """
        mode = str(self.follow_mode_combo.currentData() or "both")
        p1 = self.follow_p1_combo.currentData()
        p2 = self.follow_p2_combo.currentData()
        if mode == "single_p1_program":
            return (str(p1),) if p1 is not None else ()
        if mode == "single_p2_program":
            return (str(p2),) if p2 is not None else ()
        if mode == "p1_leads":
            return (str(p2),) if p2 is not None else ()
        if mode == "p2_leads":
            return (str(p1),) if p1 is not None else ()
        if mode == "both_program":
            return tuple(str(identity) for identity in (p1, p2) if identity is not None)
        # Simulated/manual modes are intentionally not routed to the new port
        # until a non-side-effect output adapter is explicitly composed.
        return ()

    def _modular_follow_roles(self) -> dict[str, int]:
        """Build the new port's role/controller map from page selection."""
        mode = str(self.follow_mode_combo.currentData() or "both")
        p1 = self.follow_p1_combo.currentData()
        p2 = self.follow_p2_combo.currentData()
        values: dict[str, int] = {}
        if mode in {"single_p1_program", "p2_leads", "both_program"} and p1 is not None:
            values[str(p1)] = 1
        if mode in {"single_p2_program", "p1_leads", "both_program"} and p2 is not None:
            values[str(p2)] = 2
        return values

    def _modular_follow_policy(self) -> tuple[str | None, tuple[str, ...]]:
        """Return the optional live leader and its controlled followers."""
        mode = str(self.follow_mode_combo.currentData() or "both")
        p1 = self.follow_p1_combo.currentData()
        p2 = self.follow_p2_combo.currentData()
        if mode == "p1_leads" and p1 is not None and p2 is not None:
            return str(p1), (str(p2),)
        if mode == "p2_leads" and p1 is not None and p2 is not None:
            return str(p2), (str(p1),)
        return None, ()

    def _ensure_modular_follow_adapter(self, roles: dict[str, int]) -> bool:
        """Build the concrete adapter once a successful dual seed exists."""
        if self._follow_engine_page_adapter is not None:
            self._logger.info(
                "step=follow_engine.adapter_reuse adapter_id=%s composition_id=%s stop_pending=%s start_pending=%s",
                id(self._follow_engine_page_adapter),
                id(self._follow_engine_composition) if self._follow_engine_composition is not None else None,
                bool(getattr(self, "_modular_follow_stop_pending", False)),
                bool(getattr(self, "_modular_follow_start_pending", False)),
            )
            return True
        factory = self._follow_engine_page_adapter_factory
        result = self._last_dual_first_frame_result
        snapshot = self._snapshot
        reference = self._dual_follow_reference
        if factory is None or result is None or snapshot is None or reference is None:
            return False
        try:
            from auto_modules.ui.modes.poe2_live_terrain.follow_engine_page_composition import (
                build_follow_seed_from_dual_result,
            )
            from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.models import (
                MarkerColorProfile,
            )

            configured_profiles = getattr(self.monitor_config, "dual_marker_profiles", ())
            marker_profiles = tuple(
                item if isinstance(item, MarkerColorProfile) else MarkerColorProfile.from_dict(item)
                for item in configured_profiles
            )

            seed = build_follow_seed_from_dual_result(
                map_instance=str(snapshot.metadata.instance_id),
                result=result,
                roles=roles,
                marker_profiles=marker_profiles,
                initial_candidates=getattr(self, "_dual_initial_candidates", ()),
            )
            leader_role, target_roles = self._modular_follow_policy()
            built = factory(
                seed=seed,
                monitor_config=self.monitor_config,
                wall_map=reference.wall_layer,
                native_shape=(int(snapshot.metadata.height), int(snapshot.metadata.width)),
                leader_role=leader_role,
                target_roles=target_roles,
                arm_delay_ms=int(self._FOLLOW_COMMAND_ARM_DELAY_MS),
            )
            if isinstance(built, tuple) and len(built) == 2:
                self._follow_engine_page_adapter, self._follow_engine_composition = built
                self._follow_engine_adapter_owned = True
            else:
                self._follow_engine_page_adapter = built
                self._follow_engine_composition = None
                self._follow_engine_adapter_owned = False
            return self._follow_engine_page_adapter is not None
        except Exception as exc:
            self._logger.exception("step=follow_engine.modular_adapter_build_failed")
            self.follow_status_label.setText(f"模块化跟随：适配器构建失败 | {exc}")
            return False

    def _can_async_modular_lifecycle(self) -> bool:
        return callable(getattr(getattr(self, "_follow_lifecycle_executor", None), "submit", None)) and hasattr(
            self, "_follow_lifecycle_finished"
        )

    def _submit_modular_lifecycle(self, operation: str, action: Callable[[], Any]) -> None:
        self._follow_lifecycle_serial += 1
        serial = self._follow_lifecycle_serial
        caller = " <- ".join(
            f"{frame.function}:{frame.lineno}"
            for frame in inspect.stack()[1:4]
        )
        if operation == "start":
            self._modular_follow_start_pending = True
        else:
            self._modular_follow_stop_pending = True
        self._logger.info(
            "step=follow_engine.lifecycle_submit operation=%s serial=%s caller=%s adapter_id=%s composition_id=%s active=%s start_pending=%s stop_pending=%s",
            operation, serial,
            caller,
            id(self._follow_engine_page_adapter) if self._follow_engine_page_adapter is not None else None,
            id(self._follow_engine_composition) if self._follow_engine_composition is not None else None,
            self._modular_follow_active, self._modular_follow_start_pending,
            self._modular_follow_stop_pending,
        )

        def run() -> None:
            self._logger.info(
                "step=follow_engine.lifecycle_begin operation=%s serial=%s adapter_id=%s composition_id=%s",
                operation, serial,
                id(self._follow_engine_page_adapter) if self._follow_engine_page_adapter is not None else None,
                id(self._follow_engine_composition) if self._follow_engine_composition is not None else None,
            )
            try:
                action()
            except BaseException as exc:
                self._follow_lifecycle_finished.emit(serial, operation, False, exc)
            else:
                self._follow_lifecycle_finished.emit(serial, operation, True, None)

        future = self._follow_lifecycle_executor.submit(run)
        self._follow_lifecycle_future = future

    def _on_follow_lifecycle_finished(
        self, serial: int, operation: str, success: bool, error: object,
    ) -> None:
        self._logger.info(
            "step=follow_engine.lifecycle_finished operation=%s serial=%s success=%s current_serial=%s adapter_id=%s composition_id=%s",
            operation, serial, success, self._follow_lifecycle_serial,
            id(self._follow_engine_page_adapter) if self._follow_engine_page_adapter is not None else None,
            id(self._follow_engine_composition) if self._follow_engine_composition is not None else None,
        )
        if int(serial) != int(self._follow_lifecycle_serial):
            # A later explicit stop/restart owns cleanup; stale completion must
            # never re-enable the button or resurrect a follow timer.
            return
        if operation == "start":
            self._modular_follow_start_pending = False
            if not success:
                self._logger.error("step=follow_engine.modular_start_failed_async error=%s", error)
                self._modular_follow_active = False
                self._modular_follow_live_mode = False
                # The worker action already attempted adapter/composition
                # cleanup.  Drop every owned reference here as well so a
                # retry cannot reuse a stopped ring/worker generation.
                if self._follow_engine_adapter_owned:
                    self._follow_engine_page_adapter = None
                self._follow_engine_composition = None
                self._follow_engine_adapter_owned = False
                self.follow_status_label.setText(f"模块化跟随：启动失败，已回收资源，可重试 | {error}")
                self.start_follow_button.setEnabled(True)
                self.stop_follow_button.setEnabled(False)
                return
            self._modular_follow_active = True
            modular_interval = max(
                16,
                min(100, round(1000 / max(1, int(getattr(self.monitor_config, "localization_fps", 30))))),
            )
            self._follow_timer.setInterval(modular_interval)
            self._follow_timer.start()
            self.start_follow_button.setEnabled(False)
            self.stop_follow_button.setEnabled(True)
            arm_delay_ms = int(getattr(self, "_FOLLOW_COMMAND_ARM_DELAY_MS", 0))
            self._modular_follow_arm_deadline = time.monotonic() + arm_delay_ms / 1000.0
            self._modular_follow_last_countdown = None
            self._modular_follow_poll_count = 0
            self.follow_status_label.setText(
                "模块化跟随：已启动，等待最新视觉帧；"
                + (f"{math.ceil(arm_delay_ms / 1000)}秒后允许发送，请切回 PoE2" if arm_delay_ms else "输出已待命")
            )
            self._logger.info("step=follow_engine.modular_started_async timer_interval_ms=%s", modular_interval)
            return

        self._modular_follow_stop_pending = False
        self._modular_follow_start_pending = False
        self._modular_follow_active = False
        self._modular_follow_live_mode = False
        self._follow_timer.stop()
        self._follow_timer.setInterval(self._follow_timer_default_interval)
        self._follow_engine_page_adapter = None if self._follow_engine_adapter_owned else self._follow_engine_page_adapter
        self._follow_engine_composition = None
        self._follow_engine_adapter_owned = False
        restart_requested = bool(getattr(self, "_modular_follow_restart_requested", False))
        self._modular_follow_restart_requested = False
        if restart_requested and success:
            self.start_follow_button.setEnabled(False)
            self.stop_follow_button.setEnabled(True)
            self.follow_status_label.setText("模块化跟随：旧会话已回收，正在启动新会话")
            self._logger.info("step=follow_engine.modular_restart_after_stop")
            self._start_modular_follow_experiment()
            return
        self.start_follow_button.setEnabled(
            self._dual_motion_tracker is not None
            or bool(getattr(self, "_last_dual_first_frame_result", None) and getattr(self._last_dual_first_frame_result, "accepted", False))
        )
        self.stop_follow_button.setEnabled(False)
        self.follow_status_label.setText("模块化跟随：已停止" if success else f"模块化跟随：停止完成但有错误 | {error}")

    def _start_modular_follow_experiment(self) -> bool:
        """Start the injected FollowEngine adapter without touching legacy state."""
        if bool(getattr(self, "_modular_follow_stop_pending", False)):
            self._modular_follow_restart_requested = True
            self._logger.info("step=follow_engine.modular_start_deferred reason=stop_pending")
            return True
        if bool(getattr(self, "_modular_follow_start_pending", False)):
            self._logger.info("step=follow_engine.modular_start_ignored reason=start_pending")
            return True
        roles = self._modular_follow_roles()
        if not roles:
            self.follow_status_label.setText("模块化跟随：当前模式没有程序控制角色")
            return False
        if not self._ensure_modular_follow_adapter(roles):
            return False
        adapter = self._follow_engine_page_adapter
        if adapter is None:
            return False
        if self._follow_runtime is not None or self._follow_program_output is not None:
            self._logger.warning(
                "step=follow_engine.modular_start_rejected reason=legacy_output_active"
            )
            self.stop_follow_experiment(reason="modular_start_legacy_cleanup")
        snapshot = self._snapshot
        if snapshot is None or self._dual_map_transform is None or self._dual_follow_reference is None:
            self.follow_status_label.setText("模块化跟随：请先完成地图和双人首帧")
            return False
        # The modular vision process becomes the sole live minimap owner.  Do
        # not leave the legacy Qt dual-motion worker capturing the same region
        # and mutating the old tracker while the new engine is active.
        if self._dual_motion_worker is not None or self._dual_motion_timer.isActive():
            self._logger.info("step=follow_engine.modular_takeover stopping_legacy_dual_motion=True")
            self.stop_dual_motion(clear_first_frame=False, preserve_follow=True)
        leader_role, target_roles = self._modular_follow_policy()
        self._modular_follow_live_mode = leader_role is not None and bool(target_roles)
        configure = getattr(adapter, "configure_live_follow", None)
        if callable(configure):
            configure(leader_role=leader_role, target_roles=target_roles)
        map_instance = str(snapshot.metadata.instance_id).strip()
        if not map_instance:
            self.follow_status_label.setText("模块化跟随：地图实例无效")
            return False
        start_config = FollowEngineStart(map_instance=map_instance, roles=roles)
        if self._follow_engine_composition is not None and getattr(self, "_can_async_modular_lifecycle", lambda: False)():
            self.start_follow_button.setEnabled(False)
            self.stop_follow_button.setEnabled(True)
            self.follow_status_label.setText("模块化跟随：正在后台启动 worker，请稍候")

            def start_modular() -> None:
                try:
                    adapter.start(start_config)
                except BaseException:
                    try:
                        adapter.stop(reason="start_failed")
                    finally:
                        self._follow_engine_composition.stop(reason="start_failed")
                    raise

            self._submit_modular_lifecycle("start", start_modular)
            return True
        try:
            adapter.start(start_config)
        except Exception as exc:
            self._logger.exception("step=follow_engine.modular_start_failed")
            # A failed start can leave a constructed shared ring even though
            # the port never became active. Dispose it before rebuilding from
            # a fresh seed; do not retain the failed adapter for the next click.
            try:
                adapter.stop(reason="start_failed")
            except Exception:
                self._logger.exception("step=follow_engine.modular_start_adapter_cleanup_failed")
            composition = self._follow_engine_composition
            self._follow_engine_composition = None
            if composition is not None:
                try:
                    composition.stop(reason="start_failed")
                except Exception:
                    self._logger.exception("step=follow_engine.modular_start_composition_cleanup_failed")
            if self._follow_engine_adapter_owned:
                self._follow_engine_page_adapter = None
                self._follow_engine_adapter_owned = False
            self._modular_follow_active = False
            self._modular_follow_live_mode = False
            self.follow_status_label.setText(f"模块化跟随：启动失败，已回收资源，可重试 | {exc}")
            return False
        self._modular_follow_active = True
        # Drain the latest-only port at the same cadence as the configured
        # visual sampler.  The old 100 ms experiment timer is too slow for a
        # 30 FPS stream and needlessly increases target/observation age; the
        # timer callback is non-blocking, so this does not serialize capture
        # or control work onto the UI thread.
        modular_interval = max(
            16,
            min(
                100,
                round(1000 / max(1, int(getattr(self.monitor_config, "localization_fps", 30)))),
            ),
        )
        self._follow_timer.setInterval(modular_interval)
        self._follow_timer.start()
        self.start_follow_button.setEnabled(False)
        self.stop_follow_button.setEnabled(True)
        arm_delay_ms = int(getattr(self, "_FOLLOW_COMMAND_ARM_DELAY_MS", 0))
        self._modular_follow_arm_deadline = time.monotonic() + arm_delay_ms / 1000.0
        self._modular_follow_last_countdown = None
        self.follow_status_label.setText(
            "模块化跟随：已启动，等待最新视觉帧；"
            + (f"{math.ceil(arm_delay_ms / 1000)}秒后允许发送，请切回 PoE2" if arm_delay_ms else "输出已待命")
        )
        self._logger.info(
            "step=follow_engine.modular_started map_instance=%s roles=%s timer_interval_ms=%s",
            map_instance, roles, self._follow_timer.interval(),
        )
        return True

    def _poll_modular_follow_engine(self) -> None:
        """Drain the injected port; never wait for a worker from the UI timer."""
        adapter = self._follow_engine_page_adapter
        if adapter is None or not self._modular_follow_active:
            return
        started = time.perf_counter()
        try:
            state = adapter.poll()
            snapshot = state.snapshot
            self._modular_follow_poll_count = int(getattr(self, "_modular_follow_poll_count", 0)) + 1
            for panel, render, value in (
                ("frame", self._render_modular_follow_frame, getattr(state, "preview_frame", None)),
                ("map", self._render_modular_follow_map, snapshot),
            ):
                try:
                    render(value)
                except Exception:
                    # Rendering is observational: retain countdown/status and
                    # keep the other panel updating if one renderer fails.
                    if self._modular_follow_poll_count == 1 or self._modular_follow_poll_count % 30 == 0:
                        self._logger.exception("step=follow_engine.preview_render_failed panel=%s", panel)
            remaining = max(0, math.ceil((getattr(self, "_modular_follow_arm_deadline", 0.0) - time.monotonic())))
            if remaining != getattr(self, "_modular_follow_last_countdown", None):
                self._modular_follow_last_countdown = remaining
                self._logger.info("step=follow_engine.focus_handoff remaining_seconds=%s nonzero_allowed=%s", remaining, remaining == 0)
            worker_fault = state.diagnostics.get("last_error") and (
                state.diagnostics.get("rebuild_in_progress")
                or any(value in {"error", "stalled", "exited", "failed"} for value in state.diagnostics.get("worker_state", {}).values())
            )
            if self._modular_follow_poll_count == 1 or self._modular_follow_poll_count % 30 == 0:
                diagnostics = state.diagnostics
                self._logger.info(
                    "step=follow_engine.page_poll count=%s active=%s snapshot_tick=%s snapshot_roles=%s "
                    "worker_state=%s worker_pids=%s output_state=%s output_diag=%s vision_seq=%s control_tick=%s last_error=%s arm_remaining=%s",
                    self._modular_follow_poll_count,
                    state.active,
                    diagnostics.get("last_parent_event", {}).get("control"),
                    tuple(getattr(snapshot, "roles", {}) or {}) if snapshot is not None else (),
                    diagnostics.get("worker_state"),
                    diagnostics.get("worker_pids"),
                    diagnostics.get("output_state"),
                    diagnostics.get("output_diagnostics"),
                    diagnostics.get("last_parent_event", {}).get("vision"),
                    diagnostics.get("last_parent_event", {}).get("control"),
                    diagnostics.get("last_error"), remaining,
                )
            if remaining:
                detail = f" | 等待恢复：{state.diagnostics['last_error']}" if worker_fault else ""
                self.follow_status_label.setText(f"模块化跟随：准备中，{remaining}秒后允许移动，请切回 PoE2{detail}")
            elif worker_fault:
                self.follow_status_label.setText(f"模块化跟随：等待恢复 | {state.diagnostics['last_error']}")
            elif snapshot is not None:
                self.follow_status_label.setText(
                    "模块化跟随：%s（%s）" % (snapshot.recovery_state, snapshot.recovery_reason)
                )
            elif state.diagnostics.get("last_error"):
                self.follow_status_label.setText(
                    f"模块化跟随：等待恢复 | {state.diagnostics['last_error']}"
                )
            if not state.active:
                self._modular_follow_active = False
                self._follow_timer.stop()
                self.start_follow_button.setEnabled(
                    self._dual_motion_tracker is not None
                    or bool(getattr(self._last_dual_first_frame_result, "accepted", False))
                )
                self.stop_follow_button.setEnabled(False)
                self._modular_follow_live_mode = False
                self._follow_timer.setInterval(self._follow_timer_default_interval)
        except Exception as exc:
            # A polling fault is non-terminal for the page; the adapter owns
            # the engine's recovery/cleanup contract.  Do not call the legacy
            # stop path, which could release an unrelated output lease.
            self._logger.exception("step=follow_engine.modular_poll_failed")
            self.follow_status_label.setText(f"模块化跟随：轮询异常，保持会话 | {exc}")
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            self._logger.debug(
                "step=follow_engine.modular_poll_timing elapsed_ms=%.3f active=%s",
                elapsed_ms, self._modular_follow_active,
            )

    def _render_modular_follow_frame(self, frame) -> None:
        """Render the newest encoded Vision payload without consuming worker queues."""
        if frame is None:
            return
        sequence = int(getattr(frame, "sequence", -1))
        if sequence <= int(getattr(self, "_modular_preview_sequence", -1)):
            return
        payload = getattr(frame, "payload", None)
        if not payload:
            return
        image = QImage.fromData(bytes(payload))
        if image.isNull():
            self._logger.warning("step=follow_engine.preview_decode_failed sequence=%s", sequence)
            return
        self._modular_preview_sequence = sequence
        self._set_preview(self.frame_preview, QPixmap.fromImage(image))
        # Processed masks remain private to Vision/Control. Clear stale legacy
        # images instead of presenting an old frame as if it were current.
        self._clear_label(self.processed_preview, "模块化 Vision：处理结果在子进程")
        self._clear_label(self.feature_preview, "模块化 Vision：匹配特征在子进程")
        self._logger.debug("step=follow_engine.preview_updated sequence=%s", sequence)

    def _render_modular_follow_map(self, snapshot) -> None:
        """Project the latest fused role positions onto the loaded large map."""
        if snapshot is None or self._dual_map_source_size is None or self._dual_map_transform is None:
            return
        roles = getattr(snapshot, "roles", {}) or {}
        players = {}
        for role_id, role_state in roles.items():
            point = getattr(role_state, "position_native", None)
            if point is None:
                continue
            players[str(role_id)] = localization_display_point(
                point,
                source_size=self._dual_map_source_size,
                transform=self._dual_map_transform,
            )
        if players:
            self.map_widget.set_overlay(
                players=players,
                target=getattr(self, "_clicked_target_display", None),
            )

    def start_follow_experiment(self, *, _sync_phase: str = "cold_start") -> None:
        """Start the modular follow session.

        The page used to fall back to the old in-process runtime when the
        modular adapter was not injected.  That fallback made a failed or
        partially configured migration look like a valid follow session and
        allowed the old timer/output ownership to re-enter after a restart.
        The formal follow button is now modular-only: the legacy algorithm
        components remain available behind the Control adapter, while the
        legacy page runtime is never constructed from this entry point.
        """
        if self._follow_engine_page_adapter is None and self._follow_engine_page_adapter_factory is None:
            self._logger.error(
                "step=follow_engine.modular_start_rejected reason=adapter_unavailable "
                "legacy_runtime_fallback_disabled"
            )
            self.follow_status_label.setText(
                "模块化跟随：新架构未就绪，已拒绝启动（旧版跟随已禁用）"
            )
            return
        # The entry point is intentionally idempotent.  Recovery callbacks and
        # rapid UI activation can arrive while an older session still owns a
        # timer, output lease, or prediction tracker; release that ownership
        # before constructing the replacement.
        self.stop_program_move_probe(reason="已切换到模块化跟随")
        self.stop_dual_target_experiment()
        self.stop_follow_experiment(reason="modular_restart")
        self._start_modular_follow_experiment()
        return

        # Kept below as unreachable source during the migration window only so
        # old helper methods can be removed in a separate cleanup change.  No
        # formal follow entry may execute this branch.
        if False:
            pass
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
            or not self._recovery_frame_usable(
                state,
                required_identities=(p1_identity, p2_identity),
            )
            or getattr(state, "recovery_requested", False)
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
                    outputs,
                    vector_transform=self._native_route_vector_for_input,
                    continuous_roles=program_roles if live_mode else (),
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
        # Arm the target source only after all localization, role selection,
        # output binding, and follower construction checks have succeeded.
        # An invalid start attempt must not leave a stale probe armed.
        self._experiment_composition.follow_probe.arm()
        self._follow_session_id = f"{self._follow_session_id}-{id(runtime):x}"
        self._experiment_runtime.start(self._follow_session_id, started_at_ms=now_ms)
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
        # The button is disabled while this session is active, but recovery
        # callbacks and automated harnesses can still re-enter the method.
        # Reclaim the old timer/output lease before replacing the runtime so a
        # second start cannot orphan a virtual controller.
        if (
            self._dual_target_runtime is not None
            or self._dual_target_timer.isActive()
            or self._dual_target_output is not None
        ):
            self._logger.info("step=dual_target.restart_previous_session")
            self.stop_dual_target_experiment()
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
        players = {str(key): point for key, point in state.players.items() if point is not None}
        self._sync_follow_role_choices(state.players)
        p1 = self.dual_target_p1_combo.currentData()
        p2 = self.dual_target_p2_combo.currentData()
        if p1 not in players or p2 not in players or p1 == p2:
            self.dual_target_status_label.setText("双人同目标：请选择两个不同且当前有效的角色")
            return
        if getattr(state, "recovery_requested", False) or not self._recovery_frame_usable(
            state, required_identities=(str(p1), str(p2)),
        ):
            self.dual_target_status_label.setText("双人同目标：定位尚未稳定")
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
        try:
            for role in roles:
                runtime.add_follower(
                    role,
                    PositionSample(
                        role, map_identity, players[role.actor_id],
                        int(captured_at_ms), 1.0, "visual",
                    ),
                    mode=ControlMode.PROGRAM,
                )
        except Exception as exc:
            try:
                output.close_all()
            except Exception:
                self._logger.exception("step=dual_target.output_cleanup_failed")
            self._logger.exception("step=dual_target.runtime_bind_failed")
            self.dual_target_status_label.setText(f"双人同目标：运行时初始化失败 | {exc}")
            return
        self._dual_target_runtime = runtime
        self._dual_target_output = output
        self._dual_target_roles = roles
        self._dual_target_observations = {}
        self._dual_target_tick_count = 0
        self._dual_target_last_program_diagnostics_at_ms = None
        # Arm only after runtime and every output binding have succeeded.  A
        # failed start must leave the probe idle for the next attempt.
        self._experiment_composition.dual_target_probe.arm()
        self.start_dual_target_button.setEnabled(False)
        self.stop_dual_target_button.setEnabled(True)
        self.dual_target_status_label.setText("双人同目标：等待地图点击，尚未发送输入")
        self._logger.info(
            "step=dual_target.ready map=%s roles=%s controllers=(1,2)",
            map_identity, tuple(role.key for role in roles),
        )

    def stop_dual_target_experiment(self, *, _preserve_recovery: bool = False) -> None:
        self._experiment_composition.dual_target_probe.stop()
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
        required_ids = tuple(role.actor_id for role in self._dual_target_roles)
        if getattr(state, "recovery_requested", False) or not self._recovery_frame_usable(
            state, required_identities=required_ids,
        ):
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
        caller = " <- ".join(
            f"{frame.function}:{frame.lineno}"
            for frame in inspect.stack()[1:5]
        )
        self._logger.warning(
            "step=follow_engine.stop_requested reason=%s caller=%s active=%s start_pending=%s "
            "stop_pending=%s lifecycle_serial=%s poll_count=%s adapter_id=%s composition_id=%s",
            reason, caller, self._modular_follow_active,
            self._modular_follow_start_pending, self._modular_follow_stop_pending,
            self._follow_lifecycle_serial,
            getattr(self, "_modular_follow_poll_count", 0),
            id(self._follow_engine_page_adapter) if self._follow_engine_page_adapter is not None else None,
            id(self._follow_engine_composition) if self._follow_engine_composition is not None else None,
        )
        self._experiment_composition.follow_probe.stop()
        if self._modular_follow_stop_pending:
            self._logger.info(
                "step=follow_engine.stop_coalesced reason=stop_already_pending serial=%s",
                self._follow_lifecycle_serial,
            )
            return
        if self._modular_follow_active or self._modular_follow_start_pending or self._modular_follow_stop_pending:
            adapter = self._follow_engine_page_adapter
            composition = self._follow_engine_composition
            if getattr(self, "_can_async_modular_lifecycle", lambda: False)() and composition is not None:
                self._modular_follow_active = False
                self._modular_follow_live_mode = False
                self._follow_timer.stop()
                self.start_follow_button.setEnabled(False)
                self.stop_follow_button.setEnabled(False)
                self.follow_status_label.setText("模块化跟随：正在后台停止并回收资源")

                def cleanup_modular() -> None:
                    first_error = None
                    try:
                        if adapter is not None:
                            adapter.stop(reason=reason)
                    except BaseException as exc:
                        first_error = exc
                    try:
                        composition.stop(reason=reason)
                    except BaseException as exc:
                        first_error = first_error or exc
                    if first_error is not None:
                        raise first_error

                self._submit_modular_lifecycle("stop", cleanup_modular)
                return
            try:
                if adapter is not None:
                    adapter.stop(reason=reason)
            except Exception:
                self._logger.exception("step=follow_engine.modular_stop_failed")
            finally:
                self._follow_engine_composition = None
                if composition is not None:
                    try:
                        composition.stop(reason=reason)
                    except Exception:
                        self._logger.exception("step=follow_engine.modular_composition_stop_failed")
                if self._follow_engine_adapter_owned:
                    self._follow_engine_page_adapter = None
                    self._follow_engine_adapter_owned = False
                self._modular_follow_active = False
                self._modular_follow_live_mode = False
                self._follow_timer.setInterval(self._follow_timer_default_interval)
                self._follow_timer.stop()
                self.start_follow_button.setEnabled(
                    self._dual_motion_tracker is not None
                    or bool(getattr(self._last_dual_first_frame_result, "accepted", False))
                )
                self.stop_follow_button.setEnabled(False)
                self.follow_status_label.setText("模块化跟随：已停止")
                self._logger.info("step=follow_engine.modular_stopped reason=%s", reason)
            return
        reason = self._follow_stop_reason or reason
        self._follow_stop_reason = None
        self._follow_recovery_pending = False
        self._follow_recovery_episode_active = False
        self._follow_recovery_episode_reason = None
        self._follow_recovery_episode_suppressed = 0
        was_active = self._follow_runtime is not None or self._follow_timer.isActive()
        self._experiment_runtime.stop()
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
        self._click_target_source.set(None)
        self.map_widget.set_target(None)
        if had_target:
            self._logger.info("step=map_click.cleared reason=%s", reason)

    def _on_follow_map_click(self, display_x: float, display_y: float) -> None:
        if (
            (self._follow_runtime is not None and self._follow_live_mode)
            or (self._modular_follow_active and self._modular_follow_live_mode)
        ):
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
        self._click_target_source.set(self._clicked_target_native)
        self.map_widget.set_target(self._clicked_target_display)
        mode = "program_probe" if self._program_probe_waiting_click else (
            "dual_target" if self._dual_target_runtime is not None else (
                "modular_follow" if self._modular_follow_active else (
                    "follow" if self._follow_runtime is not None else "display_only"
                )
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
        if self._program_probe_waiting_click:
            self._experiment_composition.move_probe.select(point)
        elif self._dual_target_runtime is not None:
            self._experiment_composition.dual_target_probe.select(point)
        elif self._follow_runtime is not None:
            self._experiment_composition.follow_probe.update_from_source(point)
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
        if self._modular_follow_active:
            adapter = self._follow_engine_page_adapter
            roles = self._modular_follow_target_roles()
            if adapter is None or not roles:
                self.follow_status_label.setText("模块化跟随：当前模式没有可更新的程序角色")
                return
            try:
                for role_id in roles:
                    adapter.target_clicked(role_id, self._clicked_target_native)
                if not self._follow_timer.isActive():
                    self._follow_timer.start()
                self.follow_status_label.setText(
                    f"模块化跟随：目标已更新 ({point[0]:.1f}, {point[1]:.1f})"
                )
                self._logger.info(
                    "step=follow_engine.modular_target_changed roles=%s native=%s display=%s",
                    roles, self._clicked_target_native, self._clicked_target_display,
                )
            except Exception as exc:
                self._logger.exception("step=follow_engine.modular_target_failed")
                self.follow_status_label.setText(f"模块化跟随：目标更新异常，保持会话 | {exc}")
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
            # owns the complete boundary: foreground check -> ten-second
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
        self._follow_tick_timing_sequence += 1
        self._follow_tick_timing = {
            "attempt": float(attempt),
            "sequence": float(self._follow_tick_timing_sequence),
        }
        try:
            self._follow_tick_attempt_count = attempt
            self._tick_follow_experiment_impl()
        except Exception as exc:
            self._logger.exception("step=follow_experiment.tick_failed error=%s", exc)
            self._continue_follow_after_runtime_failure(
                f"tick_exception:{type(exc).__name__}", exc,
            )
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            timing = self._follow_tick_timing or {}
            timing["total_tick_ms"] = elapsed_ms
            timing.setdefault("outcome", "exception")
            # Debug contains every tick; info is sampled to keep diagnostics
            # from becoming the bottleneck it is measuring.
            message = (
                "step=follow_experiment.timing attempt=%s total_tick_ms=%.3f "
                "context_ms=%.3f foreground_gate_ms=%.3f command_delay_gate_ms=%.3f "
                "live_context_ms=%.3f visual_state_ms=%.3f target_update_ms=%.3f "
                "prediction_update_ms=%.3f runtime_tick_ms=%.3f output_apply_ms=%.3f "
                "local_contact_ms=%.3f overlay_render_ms=%.3f diagnostic_log_ms=%.3f "
                "outcome=%s"
            )
            args = (
                attempt, elapsed_ms,
                timing.get("context_ms", 0.0), timing.get("foreground_gate_ms", 0.0),
                timing.get("command_delay_gate_ms", 0.0), timing.get("live_context_ms", 0.0),
                timing.get("visual_state_ms", 0.0), timing.get("target_update_ms", 0.0),
                timing.get("prediction_update_ms", 0.0), timing.get("runtime_tick_ms", 0.0),
                timing.get("output_apply_ms", 0.0), timing.get("local_contact_ms", 0.0),
                timing.get("overlay_render_ms", 0.0), timing.get("diagnostic_log_ms", 0.0),
                timing.get("outcome", "unknown"),
            )
            self._logger.debug(message, *args)
            if attempt <= 2 or attempt % 10 == 0 or timing.get("outcome") in {"reanchor", "exception"}:
                self._logger.info(message, *args)
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
            self._follow_tick_timing = None

    def _mark_follow_timing(self, name: str, started: float) -> None:
        timing = self._follow_tick_timing
        if timing is not None:
            timing[name] = (time.perf_counter() - started) * 1000.0

    def _add_follow_timing(self, name: str, started: float) -> None:
        timing = self._follow_tick_timing
        if timing is not None:
            timing[name] = timing.get(name, 0.0) + (time.perf_counter() - started) * 1000.0

    def _follow_timing_outcome(self, value: str) -> None:
        if self._follow_tick_timing is not None:
            self._follow_tick_timing["outcome"] = value

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
        return observation.state in {FollowState.ARRIVED, FollowState.FOLLOW_HOLD} or observation.reason in {
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
        self._poll_live_memory_reanchor()
        tick_attempt = self._follow_tick_attempt_count
        tick_started = time.perf_counter()
        context_started = time.perf_counter()
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
            self._mark_follow_timing("context_ms", context_started)
            self._follow_timing_outcome("missing_context")
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
        self._mark_follow_timing("context_ms", context_started)
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
        gate_started = time.perf_counter()
        if self._follow_program_roles and not self._gate_live_follow_foreground(
            state=state,
            captured_at_ms=self._latest_dual_captured_at_ms,
            now_ms=now_ms,
        ):
            self._mark_follow_timing("foreground_gate_ms", gate_started)
            self._follow_timing_outcome("waiting_foreground")
            self._logger.debug(
                "step=follow_experiment.tick_end attempt=%s outcome=waiting_foreground "
                "foreground=%s pid=%s hwnd=%s",
                tick_attempt,
                self._follow_foreground_wait_started_ms is not None,
                self._follow_game_pid,
                self._follow_game_hwnd,
            )
            return
        self._mark_follow_timing("foreground_gate_ms", gate_started)
        not_before_ms = self._follow_output_not_before_ms
        delay_started = time.perf_counter()
        if self._follow_program_roles and not_before_ms is not None and now_ms < not_before_ms:
            self._mark_follow_timing("command_delay_gate_ms", delay_started)
            self._follow_timing_outcome("command_delay")
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
        self._mark_follow_timing("command_delay_gate_ms", delay_started)
        if self._follow_program_roles and not_before_ms is not None:
            self._follow_output_not_before_ms = None
            self._follow_output_delay_last_log_at_ms = None
            self._logger.info(
                "step=follow_experiment.command_delay_elapsed program_roles=%s",
                tuple(role.key for role in self._follow_program_roles),
            )
        if self._follow_live_mode:
            live_context_started = time.perf_counter()
            captured_at_ms = self._latest_dual_captured_at_ms
            leader = self._follow_leader_role
            if (
                state is None or leader is None or self._snapshot is None
                or runtime.map_identity.map_id != str(self._snapshot.metadata.area_id)
                or runtime.map_identity.map_version != str(self._snapshot.metadata.instance_id)
            ):
                self._mark_follow_timing("live_context_ms", live_context_started)
                self._follow_timing_outcome("live_context_wait")
                self._follow_recovery_pending = True
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                self.follow_status_label.setText("实时跟随：等待地图/定位上下文恢复，跟随会话继续")
                self._schedule_live_follow_recovery_retry("tick_live_context_changed")
                return
            self._mark_follow_timing("live_context_ms", live_context_started)
            visual_state_started = time.perf_counter()
            roles = (leader, *self._follow_program_roles)
            role_tracker = self._follow_role_tracker
            role_observations = state.diagnostics.get("role_observations", {})
            frame_age_ms = None if captured_at_ms is None else now_ms - int(captured_at_ms)
            frame_is_stale = (
                captured_at_ms is None
                or frame_age_ms > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS
            ) and not self._follow_recovery_pending
            # A recovery episode deliberately preserves the last state while
            # a fresh worker is being built.  Treat that preserved state like
            # an observation gap: it may drive prediction, but it must not be
            # reseeded as a new visual anchor.
            visual_frame_untrusted = frame_is_stale or self._follow_recovery_pending
            # Keep a monotonic local clock for prediction samples when the
            # capture provider has not supplied a timestamp at all.  The
            # ``frame_is_stale`` flag remains true, so this fallback can never
            # be mistaken for a fresh visual frame or enter cold-start sync.
            if captured_at_ms is None:
                captured_at_ms = now_ms
            warmup_assumed_stationary = bool(
                state.diagnostics.get("warmup_assumed_stationary", False)
            )
            if frame_is_stale:
                if self._follow_stale_since_ms is None:
                    self._follow_stale_since_ms = now_ms
                if not self._follow_stale_release_sent:
                    # A delayed capture is an observation gap, not proof that
                    # the controlled role stopped. Keep command odometry alive
                    # so the motion runtime can use contact/no-progress evidence
                    # instead of turning one slow frame into a stop.
                    self._follow_stale_release_sent = True
                    self._logger.warning(
                        "step=live_role_follow.visual_gap_hold status=%s "
                        "frame_age_ms=%s leader=%s prediction_continues=True",
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
                self.follow_status_label.setText("实时跟随：视觉帧延迟，按运动预测继续")
            if self._follow_stale_since_ms is not None:
                if not visual_frame_untrusted:
                    self._logger.info(
                        "step=live_role_follow.visual_frame_resumed stale_duration_ms=%s",
                        max(0, now_ms - self._follow_stale_since_ms),
                    )
                    self._follow_stale_since_ms = None
                    self._follow_stale_release_sent = False
                    self._follow_stale_recovery_requested = False
            if role_tracker is None or warmup_assumed_stationary:
                self._mark_follow_timing("visual_state_ms", visual_state_started)
                self._follow_timing_outcome("visual_state_wait")
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                self.follow_status_label.setText("实时跟随：等待可信双人位置，当前保持中立并继续跟踪")
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
                (
                    getattr(state, "recovery_requested", False)
                    and not self._is_marker_only_recovery_state(state)
                )
                or (
                    state.status not in {"tracking", "degraded"}
                    and not self._is_marker_only_recovery_state(state)
                )
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
                self._mark_follow_timing("visual_state_ms", visual_state_started)
                self._follow_timing_outcome("reanchor")
                return
            if (
                self._follow_sync_phase in {"cold_start", "recovery_sync"}
                and not self._follow_recovery_pending
                and not visual_frame_untrusted
            ):
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
                    # A fresh wall-trusted frame may contain a temporary
                    # marker dropout.  Every role already has a bounded seed
                    # from the accepted start frame, so keep the session
                    # moving from those estimates instead of holding the
                    # output until both markers happen to be visible in the
                    # same capture.  This is still a sync promotion, not a
                    # visual acceptance: missing roles remain prediction-only
                    # until their marker returns.
                    wall_trusted = bool(state.diagnostics.get("wall_trusted", False))
                    seeded_roles = all(
                        role_tracker.estimate(role.key, now_ms=now_ms) is not None
                        for role in roles
                    )
                    if (
                        seeded_roles
                        and state.status in {"tracking", "degraded"}
                        and wall_trusted
                    ):
                        self._follow_sync_phase = "tracking"
                        self._follow_sync_frame_count += 1
                        live_sync_pending = False
                        self._logger.info(
                            "step=live_role_follow.sync_degraded "
                            "reason=marker_dropout_prediction_seeded "
                            "captured_at_ms=%s status=%s",
                            captured_at_ms, state.status,
                        )
                    else:
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
                    not visual_frame_untrusted
                    and (
                        bool(info.get("visible")) if isinstance(info, dict)
                        else state.status == "tracking" and state.players.get(role.actor_id) is not None
                    )
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
                    # A missing leader marker is an observation gap, not a
                    # terminal follow condition.  Keep the last target and
                    # let the next fresh frame correct it; stopping here made
                    # a short overlap/occlusion abort an otherwise valid run.
                    source = "target_hold"
                else:
                    # Command odometry is the fallback while a follower's
                    # marker is hidden.  Its uncertainty is diagnostic data,
                    # not permission to stop or launch an expensive global
                    # re-anchor.  Contact/no-progress evidence from the
                    # motion runtime remains the recovery authority.
                    if estimate.uncertainty_native > 12.0 or visual_age_ms > self._FOLLOW_RUNTIME_MAX_FRAME_AGE_MS:
                        if self._follow_tick_count == 1 or self._follow_tick_count % 10 == 0:
                            self._logger.warning(
                                "step=live_role_follow.prediction_unbounded_hold "
                                "role=%s visual_age_ms=%s uncertainty=%.3f "
                                "output_since_visual=%s",
                                role.key,
                                visual_age_ms,
                                estimate.uncertainty_native,
                                role_tracker.has_output_since_visual(role.key),
                            )
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
            target_update_started = time.perf_counter()
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
            self._mark_follow_timing("target_update_ms", target_update_started)
            self._mark_follow_timing("visual_state_ms", visual_state_started)
        else:
            target_update_started = time.perf_counter()
            runtime.refresh_simulated_target(now_ms=now_ms)
            self._mark_follow_timing("target_update_ms", target_update_started)
        prediction_update_started = time.perf_counter()
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
        self._mark_follow_timing("prediction_update_ms", prediction_update_started)
        runtime_started = time.perf_counter()
        observations = runtime.tick(now_ms=now_ms)
        self._mark_follow_timing("runtime_tick_ms", runtime_started)
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
                self._live_global_reanchor.start(
                    recovery.reason, preserve_follow=True
                )
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
            output_started = time.perf_counter()
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
                        contact_started = time.perf_counter()
                        self._update_follow_local_contact(
                            runtime, state, role, observation, log_step="live_role_follow",
                            emit_log=self._follow_tick_count == 1 or self._follow_tick_count % 5 == 0,
                        )
                        self._add_follow_timing("local_contact_ms", contact_started)
                self._mark_follow_timing("output_apply_ms", output_started)
            except Exception as exc:
                self._mark_follow_timing("output_apply_ms", output_started)
                self._logger.exception("step=follow_experiment.program_output_failed error=%s", exc)
                self._continue_follow_after_runtime_failure(
                    f"program_output_exception:{type(exc).__name__}", exc,
                )
                return
        elif self._follow_program_output is not None and live_sync_pending:
            output_started = time.perf_counter()
            self._follow_program_output.release_all()
            self._mark_follow_timing("output_apply_ms", output_started)
        diagnostic_started = time.perf_counter()
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
        self._mark_follow_timing("diagnostic_log_ms", diagnostic_started)
        if self._follow_live_mode:
            self._publish_follow_prediction_hints()
        overlay_started = time.perf_counter()
        self._render_follow_overlay()
        self._mark_follow_timing("overlay_render_ms", overlay_started)
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
        self._follow_timing_outcome("tracking")

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
                (
                    bool(info.get("visible"))
                    or (
                        str(getattr(state, "status", "")) == "degraded"
                        and bool((getattr(state, "diagnostics", {}) or {}).get("wall_trusted", False))
                        and bool(info.get("available"))
                        and role != self._follow_leader_role
                    )
                ) if isinstance(info, dict)
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
        reanchor_started = time.perf_counter()
        preserve_follow = bool(self._follow_live_mode and self._follow_runtime is not None)
        if preserve_follow:
            # Once an episode owns recovery, repeated timer ticks must not
            # keep re-running policy or arm more backends for the same stale
            # observation.  The next accepted frame or backend completion
            # clears the episode.
            if self._follow_recovery_episode_active:
                self._follow_recovery_episode_suppressed += 1
                if self._follow_recovery_episode_suppressed == 1 or (
                    self._follow_recovery_episode_suppressed % 25 == 0
                ):
                    self._logger.info(
                        "step=live_role_follow.recovery_episode_suppressed reason=%s count=%s",
                        reason, self._follow_recovery_episode_suppressed,
                    )
                return
            now_ms = int(time.time() * 1000)
            captured_at_ms = self._latest_dual_captured_at_ms
            frame_age_ms = (
                None if captured_at_ms is None else max(0, now_ms - int(captured_at_ms))
            )
            stale_duration_ms = (
                0 if self._follow_stale_since_ms is None
                else max(0, now_ms - int(self._follow_stale_since_ms))
            )
            decision = self._live_recovery_policy.decide(
                now_ms=now_ms,
                frame_available=captured_at_ms is not None,
                frame_age_ms=frame_age_ms,
                visual_score=None,
                local_score=None,
                consecutive_visual_failures=(
                    max(1, len(self._follow_rejected_visual))
                    if stale_duration_ms <= 0
                    else max(1, int(stale_duration_ms // 100))
                ),
                prediction_uncertainty=min(200.0, stale_duration_ms * 0.08),
                last_memory_ms=self._dual_last_recovery_at_ms,
            )
            self._logger.info(
                "step=live_role_follow.recovery_decision action=%s state=%s "
                "reason=%s frame_age_ms=%s cooldown_remaining_ms=%s",
                decision.action, decision.state.value, reason, frame_age_ms,
                decision.cooldown_remaining_ms,
            )
            if decision.action == "predict":
                self._follow_recovery_pending = True
                if self._follow_program_output is not None:
                    self._follow_program_output.release_all()
                self.follow_status_label.setText("实时跟随：视觉恢复中，按预测继续")
                return
            if decision.action == "memory":
                self._start_live_memory_reanchor(reason)
                return
        if (
            preserve_follow
            and self._dual_motion_tracker is not None
            and getattr(self._dual_motion_tracker, "matcher", None) is not None
        ):
            request_local = getattr(self._dual_motion_tracker, "request_local_correction", None)
            if callable(request_local):
                # Orientation and scale were already established by the first
                # frame.  Re-anchor around the predicted native position using
                # the existing local matcher; do not read memory or restart a
                # global first-frame registration for a runtime disturbance.
                request_local()
                self._logger.warning(
                    "step=live_role_follow.local_reanchor_requested reason=%s "
                    "memory_read=False global_registration=False prediction_continues=True request_ms=%.3f",
                    reason, (time.perf_counter() - reanchor_started) * 1000.0,
                )
                self.follow_status_label.setText(
                    "实时跟随：局部墙体重锚中，按大地图预测继续"
                )
                return
        if preserve_follow:
            self._begin_live_follow_recovery_episode(reason)
        if not self._claim_dual_recovery(reason=f"follow:{reason}"):
            self._logger.warning(
                "step=live_role_follow.reanchor_rejected reason=%s "
                "tick=%s attempts=%s request_ms=%.3f last_observations=%s last_visual_positions=%s",
                reason,
                self._follow_tick_count,
                self._follow_tick_attempt_count,
                (time.perf_counter() - reanchor_started) * 1000.0,
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
            "last_visual_positions=%s output_snapshot=%s request_ms=%.3f",
            reason,
            self._follow_tick_count,
            self._follow_tick_attempt_count,
            self._follow_sync_phase,
            self._follow_rejected_visual,
            self._follow_occluded_roles,
            self._last_follow_observations,
            self._follow_last_visual_positions,
            None if self._follow_program_output is None else self._follow_program_output.snapshot(),
            (time.perf_counter() - reanchor_started) * 1000.0,
        )
        if preserve_follow:
            self._logger.warning(
                "step=live_role_follow.reanchor_backend backend=global_async "
                "policy=frame_first reason=%s legacy_direct_entry=False",
                reason,
            )
        self._follow_recovery_pending = preserve_follow
        self._save_dual_follow_recovery_context()
        if self._follow_program_output is not None:
            self._follow_program_output.release_all()
        if preserve_follow:
            self._live_global_reanchor.start(reason, preserve_follow=True)
        else:
            self._live_global_reanchor.start(reason, preserve_follow=False)

    def _start_live_memory_reanchor(self, reason: str) -> None:
        """Start one non-blocking dual memory read for the live session."""
        if self._live_memory_future is not None and not self._live_memory_future.done():
            self._logger.info(
                "step=live_role_follow.memory_reanchor_coalesced reason=%s", reason
            )
            return
        if self._snapshot is None or self._follow_runtime is None:
            self._logger.warning(
                "step=live_role_follow.memory_reanchor_skipped reason=%s "
                "missing_snapshot_or_runtime=True", reason
            )
            return
        instance_id = str(self._snapshot.metadata.instance_id)
        source = self.dual_player_position_source or Poe2DualPlayerPositionSource()
        orientation = self._map_orientation()
        native_shape = (int(self._snapshot.metadata.height), int(self._snapshot.metadata.width))
        provider = Poe2DualMemoryAnchorProvider(source, orientation, native_shape)
        self._follow_recovery_pending = True
        self._live_memory_started_at_ms = int(time.time() * 1000)
        self._dual_last_recovery_at_ms = self._live_memory_started_at_ms
        self._logger.warning(
            "step=live_role_follow.memory_reanchor_started reason=%s instance=%s",
            reason, instance_id,
        )
        self._live_memory_future = self._live_memory_executor.submit(
            provider.read_once, instance_id
        )

    def _poll_live_memory_reanchor(self) -> None:
        future = self._live_memory_future
        if future is None or not future.done():
            return
        self._live_memory_future = None
        started_ms = self._live_memory_started_at_ms or int(time.time() * 1000)
        elapsed_ms = max(0, int(time.time() * 1000) - started_ms)
        try:
            anchors = future.result()
            tracker = self._follow_role_tracker
            runtime = self._follow_runtime
            if tracker is None or runtime is None:
                raise RuntimeError("follow tracker/runtime unavailable")
            roles = tuple(
                role for role in (self._follow_leader_role, *self._follow_program_roles)
                if role is not None
            )
            applied = 0
            for role in roles:
                anchor = anchors.get(role.actor_id)
                if anchor is None:
                    for key, candidate in anchors.items():
                        if str(key).endswith(str(role.actor_id)):
                            anchor = candidate
                            break
                if anchor is None:
                    continue
                tracker.seed(
                    role.key,
                    runtime.map_identity.map_version,
                    tuple(float(value) for value in anchor.position),
                    captured_at_ms=int(anchor.captured_at_ms),
                )
                self._follow_last_visual_positions[role.key] = tuple(
                    float(value) for value in anchor.position
                )
                self._follow_last_visual_at_ms[role.key] = int(anchor.captured_at_ms)
                applied += 1
            if applied != len(roles):
                raise RuntimeError(
                    f"memory reanchor returned {applied} of {len(roles)} follow roles"
                )
            self._follow_recovery_pending = False
            self._follow_recovery_retry_scheduled = False
            self._logger.info(
                "step=live_role_follow.memory_reanchor_success applied=%s elapsed_ms=%s",
                applied, elapsed_ms,
            )
            self.follow_status_label.setText("实时跟随：内存快速校准完成，继续跟随")
        except Exception as exc:
            self._logger.exception(
                "step=live_role_follow.memory_reanchor_failed elapsed_ms=%s error=%s "
                "fallback=global_async",
                elapsed_ms, exc,
            )
            # The old worker is now an explicit final global-recovery backend,
            # reached only after the new frame/local/prediction/memory layers.
            if self._follow_runtime is not None and self._follow_live_mode:
                self._live_global_reanchor.start(
                    f"memory_failed:{reason if 'reason' in locals() else 'unknown'}",
                    preserve_follow=True,
                )

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
        if self._follow_live_mode:
            # The live path deliberately does not call the legacy episode
            # controller.  Its retry timer is only a bounded fallback after
            # latest-frame/local attempts have been exhausted.
            delay_ms = self._follow_recovery_retry_delay_ms or 5_000
            self._logger.info(
                "step=live_role_follow.recovery_policy policy=frame_first "
                "legacy_controller_used=False reason=%s",
                reason,
            )
        else:
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
            self._live_global_reanchor.start(reason, preserve_follow=True)

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

    def _show_error(self, error: Exception) -> None:
        self.status_label.setText("状态：错误")
        self.error_label.setText(f"错误：{error}")

    def suspend(self) -> None:
        """Release active side effects while the tab is hidden.

        Hiding the host page is a temporary lifecycle transition.  Stop
        timers, workers and output leases without marking this page closed so
        it can be reused when the tab is shown again.
        """
        if self._closing:
            return
        self._logger.info("step=test_page.suspend reason=page_hidden")
        self.stop_program_move_probe(reason="页面隐藏")
        # Hiding the host page is a terminal boundary for every experiment
        # that can own a program output lease.  The visual worker may be
        # restarted when the tab is shown again, but follow and dual-target
        # timers must not continue driving controllers while their canvas is
        # hidden.
        self.stop_follow_experiment()
        self.stop_dual_target_experiment()
        self.stop_dual_motion()
        self.stop_preview()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        if self._live_memory_future is not None:
            self._live_memory_future.cancel()
            self._live_memory_future = None

    def shutdown(self) -> None:
        self._logger.warning(
            "step=follow_engine.lifecycle_shutdown_begin active=%s start_pending=%s stop_pending=%s serial=%s",
            self._modular_follow_active, self._modular_follow_start_pending,
            self._modular_follow_stop_pending, self._follow_lifecycle_serial,
        )
        self._closing = True
        self._invalidate_dual_motion_session()
        self.stop_program_move_probe()
        self.stop_follow_experiment()
        self.stop_dual_target_experiment()
        self.stop_dual_motion()
        self.stop_preview()
        self.stop_hybrid_localization()
        self.stop_multiframe_localization()
        if self._live_memory_future is not None:
            self._live_memory_future.cancel()
            self._live_memory_future = None
        # A close is a hard resource boundary: do not let Qt and the Host
        # manager exit while the serialized lifecycle task still owns worker
        # processes or a controller lease.  The task itself has bounded worker
        # stop timeouts; wait only for that bounded cleanup, then report a
        # residual task instead of silently abandoning it.
        lifecycle_future = self._follow_lifecycle_future
        if lifecycle_future is not None and not lifecycle_future.done():
            try:
                lifecycle_future.result(timeout=4.0)
            except TimeoutError:
                self._logger.error("step=follow_engine.lifecycle_shutdown_timeout serial=%s", self._follow_lifecycle_serial)
            except BaseException:
                self._logger.exception("step=follow_engine.lifecycle_shutdown_task_failed")
        self._live_memory_executor.shutdown(wait=True, cancel_futures=True)
        self._follow_lifecycle_executor.shutdown(wait=True, cancel_futures=True)
        self._logger.info("step=follow_engine.lifecycle_shutdown_finished")
        if self.capture_monitor_window is not None:
            self.capture_monitor_window.close()
        self.localization_control_dialog.close()
        if getattr(self, "_log_handler", None) is not None:
            self._logger.removeHandler(self._log_handler)
            self._log_handler.deleteLater()
        self.service.reset()


__all__ = ["Poe2CaptureTestPage"]

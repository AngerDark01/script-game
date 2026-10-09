"""PoE2 live-terrain dependencies injected into its dedicated page."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import current_thread, local, main_thread
from typing import Any

from auto_modules.adapters.platform.screen_capture import SquareScreenCapture
from auto_modules.core.vision import HSVRecognizer
from auto_modules.features.poe2.live_terrain import (
    CaptureSampleArchive,
    MonitorFrameSource,
    Poe2CaptureAdapter,
    Poe2HybridFailureArchive,
    Poe2HybridProductRuntime,
    Poe2MonitorConfigStore,
    Poe2MonitorProfileStore,
    Poe2PlayerPositionSource,
    Poe2TerrainService,
    Poe2StitchingArchive,
    Poe2StitchingSession,
    TerrainDebugArchive,
    get_terrain_logger,
)
from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.composition import (
    build_poe2_hybrid_localization_experiment,
)
from auto_modules.features.poe2.live_terrain.experimental.multiframe_localization.composition import (
    build_poe2_multiframe_experiment,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.composition import (
    build_poe2_dual_localization_experiment,
)
from auto_modules.features.poe2.live_terrain.experimental.multiplayer_localization.memory_anchors import (
    Poe2DualPlayerPositionSource,
)
from auto_modules.paths import data_root
from auto_modules.ui.modes.poe2_live_terrain.follow_engine_page_composition import (
    build_poe2_follow_engine_page_adapter,
)


@dataclass(frozen=True)
class Poe2LiveTerrainComposition:
    """Concrete PoE2 feature dependencies consumed by the UI page."""

    service: Poe2TerrainService
    runtime: Poe2HybridProductRuntime
    config_store: Poe2MonitorConfigStore
    profile_store: Poe2MonitorProfileStore
    capture_test_service: Poe2TerrainService
    capture_test_archive: TerrainDebugArchive
    capture_sample_archive: CaptureSampleArchive
    capture_stitching_archive: Poe2StitchingArchive
    capture_stitching_session_factory: Any
    capture_preview: Any
    capture_recognizer: Any
    player_position_source: Any
    hybrid_localization_factory: Any
    multiframe_localization_factory: Any
    dual_localization_factory: Any = None
    program_output_factory: Any = None
    follow_engine_page_adapter_factory: Any = None


class _ThreadLocalPreviewCapture:
    def __init__(self, screen_capture: Any) -> None:
        self._screen_capture = screen_capture
        self._local = local()

    def __call__(self, config: Any) -> Any:
        binding = config.binding
        if binding is None:
            raise RuntimeError("请先画框选择区域或选择人物中心点")
        backend = self._screen_capture
        if isinstance(backend, SquareScreenCapture) and current_thread() is not main_thread():
            backend = getattr(self._local, "backend", None)
            if backend is None:
                backend = SquareScreenCapture()
                self._local.backend = backend
        return MonitorFrameSource(backend).capture(
            binding,
            shape=config.shape,
            radius=config.circle_radius,
        )

    def close_current_thread(self) -> None:
        backend = getattr(self._local, "backend", None)
        if backend is not None:
            backend.close()
            self._local.backend = None


def _dedicated_poe2_recognizer(recognizer: Any) -> Any:
    """Copy the shared HSV parameters without sharing mutable recognizer state."""
    if not isinstance(recognizer, HSVRecognizer):
        return recognizer
    dedicated = HSVRecognizer()
    dedicated.set_params(recognizer.get_params())
    return dedicated


def build_poe2_live_terrain_composition(
    *,
    screen_capture: Any,
    recognizer: Any,
    writable_root: str | Path | None = None,
    program_output_factory: Any = None,
) -> Poe2LiveTerrainComposition:
    """Compose PoE2 capture/localization without coupling generic navigation UI."""
    root = Path(writable_root or data_root()).expanduser().resolve()
    feature_root = root / "poe2_live_terrain"
    config_store = Poe2MonitorConfigStore(feature_root)
    profile_store = Poe2MonitorProfileStore(feature_root / "monitor_profiles")
    if profile_store.active() is None:
        profile_store.create("默认配置")
    frame_source = MonitorFrameSource(screen_capture)
    preview_capture = _ThreadLocalPreviewCapture(screen_capture)
    poe2_recognizer = _dedicated_poe2_recognizer(recognizer)

    def capture_monitor_frame():
        active = profile_store.active()
        config = active or config_store.load()
        binding = config.binding
        if binding is None:
            raise RuntimeError("请先在 PoE2 监控配置中绑定小地图区域")
        return frame_source.capture(
            binding,
            shape=config.shape,
            radius=config.circle_radius,
        )

    def capture_preview_frame(config):
        return preview_capture(config or profile_store.active() or config_store.load())

    capture_preview_frame.close_current_thread = preview_capture.close_current_thread

    service = Poe2TerrainService(
        archive=TerrainDebugArchive(root / "poe2_live_terrain_test"),
    )
    capture_test_archive = TerrainDebugArchive(root / "poe2_live_terrain_test")
    capture_sample_archive = CaptureSampleArchive(
        root / "poe2_live_terrain_test" / "samples"
    )
    capture_stitching_archive = Poe2StitchingArchive(
        root / "poe2_live_terrain_test" / "stitching_sessions"
    )
    capture_test_service = Poe2TerrainService(
        adapter=Poe2CaptureAdapter(),
        archive=None,
    )
    player_position_source = Poe2PlayerPositionSource()
    dual_player_position_source = Poe2DualPlayerPositionSource()

    def build_hybrid_localization(snapshot, config_provider):
        return build_poe2_hybrid_localization_experiment(
            snapshot=snapshot,
            config_provider=config_provider,
            preview_capture=capture_preview_frame,
            recognizer=_dedicated_poe2_recognizer(poe2_recognizer),
            player_position_source=player_position_source,
        )

    def build_multiframe_localization(snapshot, config_provider):
        return build_poe2_multiframe_experiment(
            snapshot=snapshot,
            config_provider=config_provider,
            preview_capture=capture_preview_frame,
            recognizer=poe2_recognizer,
            player_position_source=player_position_source,
        )

    def build_dual_localization(snapshot, config_provider):
        return build_poe2_dual_localization_experiment(
            snapshot=snapshot,
            config_provider=config_provider,
            preview_capture=capture_preview_frame,
            recognizer=_dedicated_poe2_recognizer(poe2_recognizer),
            dual_player_position_source=dual_player_position_source,
        )

    def build_product_localization(snapshot, config_provider):
        config = config_provider()
        if getattr(config, "tracking_mode", "single") == "dual":
            return build_dual_localization(snapshot, config_provider)
        return build_hybrid_localization(snapshot, config_provider)

    def build_follow_engine_page_adapter(**kwargs):
        return build_poe2_follow_engine_page_adapter(
            program_output_factory=program_output_factory,
            **kwargs,
        )

    runtime = Poe2HybridProductRuntime(
        build_product_localization,
        initial_config=profile_store.active() or config_store.load(),
        logger=get_terrain_logger(),
        failure_recorder=Poe2HybridFailureArchive(
            root / "poe2_live_terrain_test" / "hybrid_failures"
        ),
    )

    return Poe2LiveTerrainComposition(
        service=service,
        runtime=runtime,
        config_store=config_store,
        profile_store=profile_store,
        capture_test_service=capture_test_service,
        capture_test_archive=capture_test_archive,
        capture_sample_archive=capture_sample_archive,
        capture_stitching_archive=capture_stitching_archive,
        capture_stitching_session_factory=Poe2StitchingSession,
        capture_preview=capture_preview_frame,
        capture_recognizer=poe2_recognizer,
        player_position_source=player_position_source,
        hybrid_localization_factory=build_hybrid_localization,
        multiframe_localization_factory=build_multiframe_localization,
        dual_localization_factory=build_dual_localization,
        program_output_factory=program_output_factory,
        follow_engine_page_adapter_factory=build_follow_engine_page_adapter,
    )

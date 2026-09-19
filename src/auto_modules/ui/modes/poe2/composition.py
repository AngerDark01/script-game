"""PoE2 live-terrain dependencies injected into its dedicated page."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_modules.features.poe2.live_terrain import (
    HSVPlayerObservationRecognizer,
    MonitorFrameSource,
    Poe2LocalizationRuntime,
    Poe2MonitorConfigStore,
    Poe2TerrainService,
    TerrainDebugArchive,
    get_terrain_logger,
)
from auto_modules.paths import data_root


@dataclass(frozen=True)
class Poe2LiveTerrainComposition:
    """Concrete PoE2 feature dependencies consumed by the UI page."""

    service: Poe2TerrainService
    runtime: Poe2LocalizationRuntime
    config_store: Poe2MonitorConfigStore


def build_poe2_live_terrain_composition(
    *,
    screen_capture: Any,
    recognizer: Any,
    writable_root: str | Path | None = None,
) -> Poe2LiveTerrainComposition:
    """Compose PoE2 capture/localization without coupling generic navigation UI."""
    root = Path(writable_root or data_root()).expanduser().resolve()
    config_store = Poe2MonitorConfigStore(root / "poe2_live_terrain")
    frame_source = MonitorFrameSource(screen_capture)

    def capture_monitor_frame():
        binding = config_store.load().binding
        if binding is None:
            raise RuntimeError("请先在 PoE2 监控配置中绑定小地图区域")
        return frame_source.capture(binding)

    runtime = Poe2LocalizationRuntime(
        capture=capture_monitor_frame,
        recognize=HSVPlayerObservationRecognizer(recognizer),
        logger=get_terrain_logger(),
    )
    service = Poe2TerrainService(
        archive=TerrainDebugArchive(root / "poe2_live_terrain_test"),
    )
    return Poe2LiveTerrainComposition(
        service=service,
        runtime=runtime,
        config_store=config_store,
    )

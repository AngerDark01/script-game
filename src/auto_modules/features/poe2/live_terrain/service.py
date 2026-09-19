"""Session facade for the PoE2 live-terrain feature."""

from __future__ import annotations

from .capture_adapter import Poe2CaptureAdapter
from .contracts import TerrainCaptureError, TerrainSessionState, TerrainSnapshot
from .debug_archive import TerrainDebugArchive
from .logging_utils import get_terrain_logger
from .memory_store import MemoryTerrainStore


class Poe2TerrainService:
    def __init__(
        self,
        adapter=None,
        store: MemoryTerrainStore | None = None,
        archive: TerrainDebugArchive | None = None,
    ) -> None:
        self.adapter = adapter or Poe2CaptureAdapter()
        self.store = store or MemoryTerrainStore()
        self.archive = archive
        self.state = TerrainSessionState.NEW
        self.last_error = ""
        self._logger = get_terrain_logger()

    def initialize(self) -> None:
        self._logger.info("step=session.initialize_start")
        self.store.clear()
        try:
            self.adapter.initialize()
        except Exception as exc:
            self.state = TerrainSessionState.ERROR
            self.last_error = str(exc)
            self._logger.exception("step=session.initialize_failed error=%s", exc)
            raise
        self.state = TerrainSessionState.READY_TO_CAPTURE
        self.last_error = ""
        self._logger.info("step=session.initialize_success state=%s", self.state.value)

    def capture(self) -> TerrainSnapshot:
        self._logger.info("step=session.capture_start state=%s", self.state.value)
        if self.state not in {TerrainSessionState.READY_TO_CAPTURE, TerrainSessionState.CAPTURED}:
            self._logger.error("step=session.capture_rejected reason=not_initialized")
            raise TerrainCaptureError("initialize the current PoE2 session before capture")
        self.store.clear()
        try:
            snapshot = self.adapter.capture()
        except Exception as exc:
            self.state = TerrainSessionState.ERROR
            self.last_error = str(exc)
            self._logger.exception("step=session.capture_failed error=%s", exc)
            raise
        self.store.replace(snapshot)
        if self.archive is not None:
            try:
                archive_path = self.archive.save(snapshot)
                self._logger.info("step=session.archive_success path=%s", archive_path)
            except Exception:
                self._logger.exception("step=session.archive_failed continue_in_memory_only")
        self.state = TerrainSessionState.CAPTURED
        self.last_error = ""
        self._logger.info("step=session.capture_success state=%s", self.state.value)
        return snapshot

    def invalidate(self) -> None:
        self.store.clear()
        self.state = TerrainSessionState.INVALIDATED
        self._logger.info("step=session.invalidated")

    def reset(self) -> None:
        self.store.clear()
        self.state = TerrainSessionState.NEW
        self.last_error = ""
        self._logger.info("step=session.reset")

    def snapshot(self) -> TerrainSnapshot | None:
        return self.store.snapshot()

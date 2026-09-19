"""PoE2 adapter for the standalone manual terrain producer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping

from auto_modules.paths import repository_root

from .contracts import TerrainCaptureError
from .logging_utils import get_terrain_logger
from .native_grid import load_native_grid

DEFAULT_PRODUCER_RELATIVE_PATH = Path(
    "experiments/live-terrain-preview/live_preview.py"
)


def _contains_checkpoint(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            "checkpoint" in str(key).lower() or _contains_checkpoint(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_checkpoint(item) for item in value)
    return False


class Poe2CaptureAdapter:
    def __init__(
        self,
        *,
        producer_script: str | Path | None = None,
        python_executable: str | Path | None = None,
        output_root: str | Path | None = None,
        runner: Callable[..., Any] = subprocess.run,
        timeout_seconds: float = 30.0,
    ) -> None:
        producer = producer_script or (
            repository_root().parent / "poe2-map-research" / DEFAULT_PRODUCER_RELATIVE_PATH
        )
        self.producer_script = Path(producer).expanduser().resolve()
        self.python_executable = str(python_executable or sys.executable)
        self.output_root = Path(output_root or self.producer_script.parent / "output").resolve()
        self._runner = runner
        self.timeout_seconds = float(timeout_seconds)
        self._logger = get_terrain_logger()

    @property
    def manifest_path(self) -> Path:
        return self.output_root / "latest.json"

    def initialize(self) -> None:
        self._logger.info("step=initialize.command script=%s", self.producer_script)
        self._run("init")
        self._logger.info("step=initialize.command_success")

    def capture(self):
        self._logger.info("step=capture.command_start script=%s", self.producer_script)
        before = self._signature(self.manifest_path)
        self._run("capture")
        after = self._signature(self.manifest_path)
        if before is not None and after == before:
            self._logger.error("step=capture.reject reason=stale_manifest path=%s", self.manifest_path)
            raise TerrainCaptureError("capture did not publish a fresh terrain manifest")
        manifest = self._read_manifest(self.manifest_path)
        native_grid = self._resolve_native_grid(manifest)
        self._logger.info("step=capture.manifest_valid native_grid=%s", native_grid)
        snapshot = load_native_grid(native_grid)
        self._logger.info(
            "step=capture.convert_success area=%s instance=%s shape=%sx%s",
            snapshot.metadata.area_id,
            snapshot.metadata.instance_id,
            snapshot.metadata.height,
            snapshot.metadata.width,
        )
        return snapshot

    def _run(self, command: str) -> None:
        if not self.producer_script.is_file():
            raise TerrainCaptureError(f"PoE2 producer script not found: {self.producer_script}")
        try:
            self._logger.info("step=producer.run command=%s", command)
            result = self._runner(
                [self.python_executable, str(self.producer_script), command],
                cwd=str(self.producer_script.parent),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._logger.exception("step=producer.start_failed command=%s", command)
            raise TerrainCaptureError(f"PoE2 {command} command failed to start: {exc}") from exc
        if getattr(result, "returncode", 1) != 0:
            detail = (getattr(result, "stderr", "") or getattr(result, "stdout", "") or "").strip()
            self._logger.error("step=producer.failed command=%s detail=%s", command, detail or "unknown error")
            raise TerrainCaptureError(f"PoE2 {command} command failed: {detail or 'unknown error'}")
        self._logger.info("step=producer.success command=%s", command)

    @staticmethod
    def _signature(path: Path) -> str | None:
        if not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _read_manifest(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            self._logger.error("step=manifest.reject reason=missing path=%s", path)
            raise TerrainCaptureError(f"capture manifest not found: {path}")
        try:
            manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self._logger.exception("step=manifest.reject reason=invalid_json path=%s", path)
            raise TerrainCaptureError("capture manifest is not valid JSON") from exc
        if not isinstance(manifest, dict):
            raise TerrainCaptureError("capture manifest must be a JSON object")
        if manifest.get("tool") != "manual-live-terrain-capture":
            self._logger.error("step=manifest.reject reason=tool_mismatch")
            raise TerrainCaptureError("capture manifest is not from the live terrain tool")
        if _contains_checkpoint(manifest):
            self._logger.error("step=manifest.reject reason=checkpoint")
            raise TerrainCaptureError("checkpoint capture output is not accepted")
        self._logger.info("step=manifest.valid path=%s", path)
        return manifest

    def _resolve_native_grid(self, manifest: Mapping[str, Any]) -> Path:
        candidate = manifest.get("native_grid") or (self.output_root / "latest.npz")
        path = Path(str(candidate)).expanduser()
        if not path.is_absolute():
            path = self.output_root / path
        path = path.resolve()
        if not path.is_relative_to(self.output_root):
            raise TerrainCaptureError("native grid path escapes the producer output directory")
        if not path.is_file():
            raise TerrainCaptureError(f"native grid not found: {path}")
        return path

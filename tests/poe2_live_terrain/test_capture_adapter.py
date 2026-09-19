import json
from types import SimpleNamespace

import numpy as np
import pytest

from auto_modules.features.poe2.live_terrain.capture_adapter import Poe2CaptureAdapter
from auto_modules.features.poe2.live_terrain.contracts import TerrainCaptureError


def _write_npz(path, *, captured_at="2026-09-19T00:00:00+00:00"):
    np.savez(
        path,
        raw_cells=np.array([[0]], dtype=np.uint8),
        cell_state=np.array([[0]], dtype=np.int8),
        known_mask=np.array([[255]], dtype=np.uint8),
        wall_layer=np.array([[255]], dtype=np.uint8),
        explored_map=np.array([[255]], dtype=np.uint8),
        metadata_json=json.dumps({
            "area_id": "Area",
            "area_hash": "h",
            "instance_id": "Area:h",
            "width": 1,
            "height": 1,
            "captured_at": captured_at,
        }),
    )


def _manifest(output, *, tool="manual-live-terrain-capture", **extra):
    value = {
        "tool": tool,
        "captured_at": "2026-09-19T00:00:00+00:00",
        "area_id": "Area",
        "area_hash": "h",
        "instance_id": "Area:h",
        "native_grid": str((output / "latest.npz").resolve()),
    }
    value.update(extra)
    (output / "latest.json").write_text(json.dumps(value), encoding="utf-8")


def test_capture_runs_producer_and_consumes_fresh_valid_output(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    script = tmp_path / "live_preview.py"
    script.write_text("# fake", encoding="utf-8")
    _write_npz(output / "latest.npz")
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        _manifest(output)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    adapter = Poe2CaptureAdapter(
        producer_script=script,
        output_root=output,
        runner=runner,
    )
    snapshot = adapter.capture()
    assert snapshot.metadata.instance_id == "Area:h"
    assert calls[0][0][-1] == "capture"


def test_capture_rejects_failed_or_stale_output(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    script = tmp_path / "live_preview.py"
    script.write_text("# fake", encoding="utf-8")
    _write_npz(output / "latest.npz")
    _manifest(output)

    def failed_runner(_command, **_kwargs):
        return SimpleNamespace(returncode=2, stdout="", stderr="no process")

    with pytest.raises(TerrainCaptureError, match="no process"):
        Poe2CaptureAdapter(producer_script=script, output_root=output, runner=failed_runner).capture()

    with pytest.raises(TerrainCaptureError, match="fresh"):
        Poe2CaptureAdapter(
            producer_script=script,
            output_root=output,
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
        ).capture()


def test_capture_rejects_checkpoint_manifest(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    script = tmp_path / "live_preview.py"
    script.write_text("# fake", encoding="utf-8")
    _write_npz(output / "latest.npz")

    def runner(_command, **_kwargs):
        _manifest(output, checkpoint_source="old")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with pytest.raises(TerrainCaptureError, match="checkpoint"):
        Poe2CaptureAdapter(producer_script=script, output_root=output, runner=runner).capture()

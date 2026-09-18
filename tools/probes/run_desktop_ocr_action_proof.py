"""Run the explicit desktop OCR-to-mapped-mouse proof in dry-run or live mode."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from auto_modules.core.actions import MouseActionAdapter
from auto_modules.adapters.input.win32_driver import InputDriver
from auto_modules.adapters.perception import (
    RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL,
    RapidOcrProvider,
    resolve_rapidocr_engine_options,
)
from auto_modules.adapters.platform import DesktopFrameSource
from auto_modules.application.workflows.desktop_ocr_action_proof import DesktopOcrActionProof, DesktopProofReport


def build_live_proof(
    *,
    model_id: str,
    model_directory: Path,
    min_confidence: float,
    double_click_interval_ms: int,
) -> DesktopOcrActionProof:
    """Compose optional OCR, desktop capture, coordinate mapping, and Win32 mouse input."""
    engine_options = resolve_rapidocr_engine_options(model_id, model_directory)
    return DesktopOcrActionProof(
        frame_source=DesktopFrameSource(),
        ocr_provider=RapidOcrProvider(engine_options=engine_options),
        action_adapter=MouseActionAdapter(device=InputDriver(), device_id="win32_mouse"),
        min_confidence=min_confidence,
        double_click_interval_ms=double_click_interval_ms,
    )


def report_as_dict(report: DesktopProofReport) -> dict[str, Any]:
    """Serialize only primitive diagnostic values for the command-line proof report."""
    geometry = report.geometry
    result: dict[str, Any] = {
        "status": report.status,
        "reason": report.reason,
        "frame_size": {"width": report.frame_size[0], "height": report.frame_size[1]},
        "physical_desktop": {
            "left": geometry.left,
            "top": geometry.top,
            "width": geometry.width,
            "height": geometry.height,
            "dpi_scale_x": geometry.dpi_scale_x,
            "dpi_scale_y": geometry.dpi_scale_y,
        },
        "detection": None,
        "mapped_point": None,
        "action": None,
    }
    if report.detection is not None:
        detection = report.detection
        result["detection"] = {
            "text": detection.text,
            "confidence": detection.confidence,
            "source_center": {"x": detection.center[0], "y": detection.center[1]},
            "bbox": None
            if detection.bbox is None
            else {
                "left": detection.bbox.left,
                "top": detection.bbox.top,
                "width": detection.bbox.width,
                "height": detection.bbox.height,
            },
            "coordinate_space": detection.coordinate_space.value,
        }
    if report.mapped_point is not None:
        point = report.mapped_point
        result["mapped_point"] = {
            "source": {"x": point.source_point.x, "y": point.source_point.y, "space": point.source_space.value},
            "destination": {
                "x": point.destination_point.x,
                "y": point.destination_point.y,
                "space": point.destination_space.value,
            },
            "mapping": dict(point.metadata),
        }
    if report.action_result is not None:
        action = report.action_result
        result["action"] = {
            "executed": action.executed,
            "kind": action.kind.value,
            "point": {"x": action.point[0], "y": action.point[1]},
            "device_id": action.device_id,
            "started_at_ms": action.started_at_ms,
            "completed_at_ms": action.completed_at_ms,
            "metadata": dict(action.metadata),
        }
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find one exact desktop OCR label, map it to physical screen coordinates, and optionally double-click it."
    )
    parser.add_argument("--text", required=True, help="Exact visible text to find through OCR")
    parser.add_argument("--execute", action="store_true", help="Perform the double click after all safety gates pass")
    parser.add_argument("--min-confidence", type=float, default=0.80, help="Minimum OCR confidence for the exact text")
    parser.add_argument("--double-click-interval-ms", type=int, default=100, help="Interval between the two clicks")
    parser.add_argument("--model", default=RAPIDOCR_PPOCR_V6_MULTILINGUAL_SMALL)
    parser.add_argument(
        "--model-directory",
        default=str(_PROJECT_ROOT / "resources" / "assets" / "perception_models"),
        help="Directory holding explicitly installed OCR recognition model assets",
    )
    return parser


def main() -> int:
    arguments = _build_parser().parse_args()
    proof = build_live_proof(
        model_id=arguments.model,
        model_directory=Path(arguments.model_directory),
        min_confidence=arguments.min_confidence,
        double_click_interval_ms=arguments.double_click_interval_ms,
    )
    report = proof.run(target_text=arguments.text, execute=arguments.execute)
    print(json.dumps(report_as_dict(report), ensure_ascii=True, indent=2))
    return 0 if report.status in {"dry_run", "executed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

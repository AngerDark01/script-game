from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Mapping

import cv2


DEBUG_ENV_VAR = "MINIMAP_COLOR_PICKER_DEBUG"


def is_wall_preview_debug_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether color-picker preview debug artifacts should be written."""
    values = os.environ if env is None else env
    return values.get(DEBUG_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def write_wall_preview_debug(
    *,
    output_dir: str | Path,
    wall_mask,
    wall_mask_before_morph,
    hsv,
    min_hsv,
    max_hsv,
    image_shape,
    wall_points,
    white_pixels: int,
    total_pixels: int,
    white_ratio: float,
    pixels_after_close: int,
    pixels_after_close_diff: int,
) -> dict[str, Path]:
    """Write color-picker preview diagnostics to an explicit debug folder."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    preview_path = output_path / f"preview_result_{timestamp}.png"
    before_morph_path = output_path / f"preview_before_morph_{timestamp}.png"
    log_path = output_path / f"preview_log_{timestamp}.txt"

    cv2.imwrite(str(preview_path), wall_mask)
    cv2.imwrite(str(before_morph_path), wall_mask_before_morph)

    with log_path.open("w", encoding="utf-8-sig") as handle:
        handle.write(f"二值化预览日志 - {datetime.now()}\n")
        handle.write(
            f"HSV范围: [{min_hsv[0]}, {min_hsv[1]}, {min_hsv[2]}] ~ "
            f"[{max_hsv[0]}, {max_hsv[1]}, {max_hsv[2]}]\n"
        )
        handle.write(f"图像尺寸: {image_shape}\n")
        handle.write(f"选择的墙体点: {len(wall_points)} 个\n")
        for index, (x, y) in enumerate(wall_points):
            if 0 <= x < hsv.shape[1] and 0 <= y < hsv.shape[0]:
                pixel_hsv = hsv[y, x]
                in_range = (pixel_hsv >= min_hsv).all() and (pixel_hsv <= max_hsv).all()
                handle.write(
                    f"点{index + 1} ({x},{y}): HSV{pixel_hsv} "
                    f"{'在范围内' if in_range else '超出范围'}\n"
                )
        handle.write(f"处理前mask白色像素: {white_pixels}/{total_pixels} ({white_ratio * 100:.2f}%)\n")
        handle.write(f"Close操作后白色像素: {pixels_after_close}/{total_pixels}\n")
        handle.write(f"形态学处理变化像素: {pixels_after_close_diff}\n")
        handle.write("[DONE] 形态学处理完成，保留了识别的墙体特征\n")

    return {
        "preview": preview_path,
        "before_morph": before_morph_path,
        "log": log_path,
    }

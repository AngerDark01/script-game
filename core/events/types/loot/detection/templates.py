from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .images import foreground_mask, to_bgr
from .models import LootPreparedTemplate, LootTemplate


def load_loot_templates(paths: list[Path]) -> list[LootTemplate]:
    templates: list[LootTemplate] = []
    for path in sorted(paths, key=lambda item: item.name):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".bmp"}:
            continue
        image, mask = read_template_image(path)
        if int(np.count_nonzero(mask)) < 20:
            continue
        templates.append(LootTemplate(name=path.stem, image=image, mask=mask))
    return templates


def read_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"image not readable: {path}")
    return to_bgr(image)


def read_template_image(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"image not readable: {path}")
    bgr = to_bgr(image)
    mask = foreground_mask(image)
    return crop_template_foreground(bgr, mask)


def crop_template_foreground(image: np.ndarray, mask: np.ndarray, padding: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Trim transparent/background padding so template matching focuses on icon structure."""
    if image.size == 0 or mask.size == 0:
        return image, mask
    if int(np.count_nonzero(mask)) <= 0:
        return image, mask

    x, y, width, height = cv2.boundingRect(mask)
    x1 = max(0, int(x) - int(padding))
    y1 = max(0, int(y) - int(padding))
    x2 = min(image.shape[1], int(x + width) + int(padding))
    y2 = min(image.shape[0], int(y + height) + int(padding))
    if x2 <= x1 or y2 <= y1:
        return image, mask
    return image[y1:y2, x1:x2].copy(), mask[y1:y2, x1:x2].copy()


def resize_template(image: np.ndarray, mask: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
    h, w = image.shape[:2]
    new_w = max(4, int(round(w * scale)))
    new_h = max(4, int(round(h * scale)))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    resized_mask = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    return resized, resized_mask


def prepare_scaled_templates(templates: list[LootTemplate], scales: list[float]) -> list[LootPreparedTemplate]:
    prepared: list[LootPreparedTemplate] = []
    scale_values = sorted({float(scale) for scale in scales if float(scale) > 0})
    for template in templates:
        for scale in scale_values:
            image, mask = resize_template(template.image, template.mask, scale)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 45, 135)
            edges = cv2.bitwise_and(edges, edges, mask=cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1))
            prepared.append(
                LootPreparedTemplate(
                    name=template.name,
                    scale=float(scale),
                    image=image,
                    mask=mask,
                    gray=gray,
                    edges=edges,
                    edge_pixels=int(np.count_nonzero(edges)),
                    mask_pixels=int(np.count_nonzero(mask)),
                )
            )
    return prepared

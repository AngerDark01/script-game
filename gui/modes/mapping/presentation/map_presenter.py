from __future__ import annotations

from dataclasses import dataclass

from ..map_renderer import pixmap_from_bgr, render_global_map_pixmap, unpack_enhanced_map_result


@dataclass(frozen=True)
class MappingDisplayResult:
    map_crop_offset: tuple[int, int]


def update_mapping_displays(
    *,
    capture_label,
    global_map_widget,
    stitcher,
    current_img,
    nav_path,
    current_crop_offset: tuple[int, int],
    last_capture_size,
    last_player_local_pos,
    player_pos=None,
    capture_size=None,
) -> MappingDisplayResult:
    if current_img is not None:
        capture_label.setPixmap(pixmap_from_bgr(current_img))

    result = stitcher.get_enhanced_map(margin=500)
    global_map, crop_x1, crop_y1 = unpack_enhanced_map_result(result)
    if global_map.size <= 0:
        return MappingDisplayResult(map_crop_offset=current_crop_offset)

    resolved_capture_size = capture_size or last_capture_size
    resolved_player_pos = player_pos or last_player_local_pos
    pixmap = render_global_map_pixmap(
        global_map=global_map,
        crop_x1=crop_x1,
        crop_y1=crop_y1,
        nav_path=nav_path,
        current_position=stitcher.get_current_position(),
        draw_scale=stitcher.draw_scale,
        player_pos=resolved_player_pos,
        capture_size=resolved_capture_size,
    )
    global_map_widget.set_image(pixmap)
    return MappingDisplayResult(map_crop_offset=(crop_x1, crop_y1))

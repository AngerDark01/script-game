from __future__ import annotations

from .models import MappingTickResult


class MappingSession:
    """Runs one capture-recognize-stitch mapping tick."""

    def __init__(self, app_context, *, get_monitor_center, get_last_player_local_pos) -> None:
        self.app_context = app_context
        self.get_monitor_center = get_monitor_center
        self.get_last_player_local_pos = get_last_player_local_pos

    def tick(self) -> MappingTickResult | None:
        if self.app_context.monitor_logical_center:
            img = self.app_context.screen_capture.capture_square(
                *self.get_monitor_center(),
                self.app_context.monitor_size,
            )
            player_pos = (
                self.app_context.monitor_size // 2,
                self.app_context.monitor_size // 2,
            )
        else:
            region = self.app_context.monitor_region
            img = self.app_context.screen_capture.capture(
                region["left"],
                region["top"],
                region["width"],
                region["height"],
            )
            player_pos = self._detect_or_fallback_player_pos(img)

        combined, wall_mask, fog_mask = self.app_context.recognizer.extract_combined(
            img,
            player_pos=player_pos,
        )
        raw_gray = self.app_context.recognizer.get_raw_gray(img)
        self.app_context.stitcher.add_frame(
            img,
            combined,
            wall_mask,
            fog_mask,
            raw_gray=raw_gray,
            player_pos=player_pos,
        )
        h_img, w_img = img.shape[:2]
        return MappingTickResult(
            current_image=self.app_context.recognizer.get_preprocessed_image(img),
            combined_mask=combined,
            player_pos=player_pos,
            capture_size=(w_img, h_img),
        )

    def _detect_or_fallback_player_pos(self, img) -> tuple[int, int]:
        player_mask = self.app_context.recognizer.extract_player(img)
        player_pos = self.app_context.tracker.detect_player(player_mask)
        if player_pos is not None:
            return player_pos

        last_player_local_pos = self.get_last_player_local_pos()
        if last_player_local_pos is not None:
            return last_player_local_pos

        h_img, w_img = img.shape[:2]
        return w_img // 2, h_img // 2

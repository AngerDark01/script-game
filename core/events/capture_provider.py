from __future__ import annotations


class StaticCaptureProvider:
    def __init__(self, minimap_frame=None, game_view_frame=None, game_view_rect=None):
        self._minimap_frame = minimap_frame
        self._game_view_frame = game_view_frame
        self._game_view_rect = game_view_rect or {"left": 0, "top": 0, "width": 0, "height": 0}

    def capture_minimap_raw(self):
        return self._minimap_frame

    def capture_game_view(self):
        return self._game_view_frame

    def game_view_rect(self):
        return self._game_view_rect


class GameWindowCaptureProvider:
    """Capture the full game window for event confirmation."""

    def __init__(self, screen_capture, window_finder=None):
        self.screen_capture = screen_capture
        self.window_finder = window_finder
        self._last_rect = {"left": 0, "top": 0, "width": 0, "height": 0}

    def capture_minimap_raw(self):
        return None

    def capture_game_view(self):
        rect = self.game_view_rect()
        if not rect or rect["width"] <= 0 or rect["height"] <= 0:
            return None
        return self.screen_capture.capture(rect["left"], rect["top"], rect["width"], rect["height"])

    def game_view_rect(self):
        if self.window_finder:
            rect = self.window_finder()
            if rect:
                self._last_rect = rect
        return self._last_rect

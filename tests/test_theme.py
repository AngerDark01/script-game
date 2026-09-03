import unittest

from gui.theme import COLORS, app_stylesheet


class ThemeTests(unittest.TestCase):
    def test_palette_contains_required_tokens(self):
        for name in ("window", "surface", "canvas", "border", "text", "muted", "primary", "success", "warning", "danger"):
            self.assertIn(name, COLORS)

    def test_stylesheet_contains_semantic_roles(self):
        stylesheet = app_stylesheet()
        for selector in ("QGraphicsView", "QPushButton[role=\"primary\"]", "QPushButton[role=\"danger\"]", "QFrame[role=\"status\"]"):
            self.assertIn(selector, stylesheet)


if __name__ == "__main__":
    unittest.main()

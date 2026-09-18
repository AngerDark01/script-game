from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from auto_modules.ui.modes.mapping.io.config_store import save_map_config


class MappingConfigPreservationTests(unittest.TestCase):
    def test_mapping_save_keeps_wall_override_metadata_owned_by_the_map_editor(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / "config.json").write_text(
                json.dumps(
                    {
                        "fps": 30,
                        "wall_overrides": {
                            "enabled": True,
                            "file": "wall_overrides.npz",
                            "format_version": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )

            save_map_config(folder, {"fps": 60, "monitor_size": 800})

            saved = json.loads((folder / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(60, saved["fps"])
            self.assertEqual(800, saved["monitor_size"])
            self.assertTrue(saved["wall_overrides"]["enabled"])


if __name__ == "__main__":
    unittest.main()

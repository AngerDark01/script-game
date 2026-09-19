from auto_modules.features.poe2.live_terrain.monitor_config import (
    Poe2MonitorConfig,
    Poe2MonitorConfigStore,
)


def test_missing_file_returns_independent_defaults(tmp_path):
    config = Poe2MonitorConfigStore(tmp_path).load()
    assert config.binding is None
    assert config.search_radius == 96


def test_save_and_load_round_trip(tmp_path):
    store = Poe2MonitorConfigStore(tmp_path)
    original = Poe2MonitorConfig(search_radius=144, match_threshold=0.82)
    path = store.save(original)
    assert path.name == "monitor.json"
    assert store.load() == original


def test_invalid_json_does_not_import_navigation_config(tmp_path):
    path = tmp_path / "monitor.json"
    path.write_text('{"monitor_region": {"left": 1}}', encoding="utf-8")
    config = Poe2MonitorConfigStore(tmp_path).load()
    assert config.binding is None

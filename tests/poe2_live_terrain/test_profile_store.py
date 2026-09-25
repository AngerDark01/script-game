from __future__ import annotations

from auto_modules.features.poe2.live_terrain.monitor_config import Poe2MonitorConfig
from auto_modules.features.poe2.live_terrain.profile_store import Poe2MonitorProfileStore


def test_profile_store_creates_lists_switches_and_deletes_profiles(tmp_path) -> None:
    store = Poe2MonitorProfileStore(tmp_path)

    first = store.create("配置 1")
    second = store.create("配置 2")
    store.activate(first.profile_id)

    assert [item.profile_name for item in store.list_profiles()] == ["配置 1", "配置 2"]
    assert store.active().profile_id == first.profile_id

    store.delete(first.profile_id)

    assert store.active().profile_id == second.profile_id


def test_profile_store_copies_and_persists_profile(tmp_path) -> None:
    store = Poe2MonitorProfileStore(tmp_path)
    source = store.create("来源")
    source = Poe2MonitorConfig.from_dict({**source.as_dict(), "search_radius": 123})
    store.save(source)

    copied = store.copy(source.profile_id, "副本")
    reloaded = Poe2MonitorProfileStore(tmp_path)

    assert copied.profile_name == "副本"
    assert reloaded.get(copied.profile_id).search_radius == 123

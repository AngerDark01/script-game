import pytest
from auto_modules.features.torchlight.follow.config import FollowConfig,FollowConfigStore


def test_config_is_versioned_and_loading_never_starts_or_arms(tmp_path):
    store=FollowConfigStore(tmp_path)
    config=FollowConfig()
    first=store.save(config)
    config.search_radius=70
    store.save(config)
    assert store.load().search_radius==70
    assert store.load(first).search_radius==100
    assert len(store.versions())==2
    assert 'armed' not in store.load().to_dict()


def test_duplicate_controller_and_reserved_hotkey_rejected():
    c=FollowConfig()
    c.actors[1]['controller']=1
    with pytest.raises(ValueError): c.validate()


def test_unrestricted_color_region_cannot_arm_even_with_parameters(tmp_path):
    p=tmp_path/'map.npz';p.touch()
    c=FollowConfig(map_path=str(p),map_id='m',leader_device='B')
    for a in c.actors:a['parameters']={'min_area':1,'max_area':100}
    with pytest.raises(ValueError,match='HSV'):c.validate(for_start=True)
    c=FollowConfig(shortcuts={'F9':'return'})
    with pytest.raises(ValueError): c.validate()

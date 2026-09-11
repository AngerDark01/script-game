import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from gui.modes.follow.page import FollowPage
from gui.modes.follow.editors import ActorEditor,ChainEditor


def test_follow_page_opens_disarmed_and_saves_versions(tmp_path):
    app=QApplication.instance() or QApplication([])
    page=FollowPage(config_root=tmp_path)
    page.resize(1100,760); page.show(); app.processEvents()
    assert page.service is None and page.tabs.count()==4
    assert page.actor_table.rowCount()==2
    page.leader_actor.setText('LeaderCustom')
    page._save(); page.radius.setValue(70); page._save()
    assert len(page.store.versions())==2
    assert page.store.load().search_radius==70
    assert page.store.load().leader_actor=='LeaderCustom'
    page.close(); page.timer.stop()


def test_actor_and_chain_editors_roundtrip():
    from core.runtime.follow_config import FollowConfig
    app=QApplication.instance() or QApplication([])
    dialog=ActorEditor(FollowConfig().actors[0])
    result=dialog.value()
    assert result['parameters']['max_area']==100
    chain=ChainEditor(dict(name='return',steps=[dict(op='button',button='A',ms=100)]))
    assert chain.value()['steps'][0]['button']=='A'
    dialog.close(); chain.close()

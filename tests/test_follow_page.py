import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from auto_modules.ui.modes.torchlight.follow.page import FollowPage
from auto_modules.ui.modes.torchlight.follow.editors import ActorEditor,ChainEditor,ParallelGroupEditor


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
    from auto_modules.features.torchlight.follow.config import FollowConfig
    app=QApplication.instance() or QApplication([])
    dialog=ActorEditor(FollowConfig().actors[0])
    result=dialog.value()
    assert result['parameters']['max_area']==100
    chain=ChainEditor(dict(name='return',steps=[dict(op='button',button='A',ms=100)]))
    assert chain.value()['steps'][0]['button']=='A'
    chain.add_track({'mode':'frequency','buttons':['LB','X'],'hold_ms':80,'interval_ms':500,'end_ms':3000})
    value=chain.value()
    assert value['tracks'][0]['buttons']==('LB','X')
    assert value['tracks'][0]['interval_ms']==500
    assert value['max_runs'] is None
    movement=ChainEditor(dict(name='move',steps=[dict(op='button',button='LS_UP_RIGHT',ms=500)],
        tracks=[dict(mode='once',buttons=['LS_LEFT'],hold_ms=300)]))
    movement_value=movement.value()
    assert movement_value['steps'][0]['button']=='LS_UP_RIGHT'
    assert movement_value['tracks'][0]['buttons']==('LS_LEFT',)
    assert '移动 左' in movement.track_table.cellWidget(0,1).text()
    dialog.close(); chain.close(); movement.close()


def test_parallel_group_editor_and_chain_roundtrip():
    app=QApplication.instance() or QApplication([])
    tracks=[
        dict(mode='continuous',buttons=['LS_RIGHT'],delay_ms=0,hold_ms=100),
        dict(mode='once',buttons=['RB'],delay_ms=200,hold_ms=100),
        dict(mode='frequency',buttons=['X','Y'],delay_ms=100,hold_ms=50,interval_ms=250,end_ms=800),
    ]
    group=ParallelGroupEditor(tracks,1000)
    assert group.value()[1]['delay_ms']==200
    assert group.value()[2]['buttons']==('X','Y')
    assert group.value()[2]['interval_ms']==250

    chain=ChainEditor(dict(name='move-and-cast',steps=[
        dict(op='parallel',ms=1000,tracks=tracks),
        dict(op='button',button='A',ms=100),
    ]))
    value=chain.value()
    assert chain.table.cellWidget(0,0).currentText()=='并行动作组'
    assert value['steps'][0]['op']=='parallel'
    assert value['steps'][0]['tracks'][0]['buttons']==['LS_RIGHT']
    assert value['steps'][0]['tracks'][1]['delay_ms']==200
    assert value['steps'][1]=={'op':'button','ms':100,'button':'A'}
    group.close(); chain.close()

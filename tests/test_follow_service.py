from auto_modules.features.torchlight.follow.service import FollowService
from auto_modules.features.torchlight.follow.config import FollowConfig


def test_network_accepts_actual_nested_sync_status(tmp_path):
    map_path=tmp_path/'map.npz'; map_path.touch()
    config=FollowConfig(map_path=str(map_path),map_id='m',leader_device='B')
    for i,actor in enumerate(config.actors): actor['parameters']={'hue_min':40+i*20,'hue_max':60+i*20,'max_area':100}
    class Client:
        def connect(self,**kw): pass
        def close(self): pass
        def request(self,name):
            if name=='sync.status': return {'ok':True,'status':{'mode':'share'}}
            service.stop_event.set()
            return {'ok':True,'status':{'sharedPositions':[]},'events':[]}
    service=FollowService(config,client_factory=Client)
    service._network()
    assert service.network_status.get('state')=='sharing'
    assert 'error' not in service.network_status
    service.stop()

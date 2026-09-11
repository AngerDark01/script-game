"""Versioned follow configuration. Loading never arms automation."""
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from math import isfinite
from uuid import uuid4
import json


@dataclass
class FollowConfig:
    role: str = 'A'
    map_path: str = ''
    map_id: str = ''
    reference_walls: str = 'base'
    roi: list = field(default_factory=lambda:[0,0,300,300])
    initial_origin: list = field(default_factory=lambda:[0.,0.])
    search_radius: int = 100
    scale: float = 1.
    period_ms: int = 50
    position_ttl_ms: int = 250
    clearance: int = 2
    leader_device: str = ''
    leader_actor: str = 'B'
    recipient_device: str = ''
    event_targets: list = field(default_factory=lambda:['A1','A2'])
    recognizer: dict = field(default_factory=dict)
    actors: list = field(default_factory=lambda:[
        dict(actor_id='A1',controller=1,lag_distance=15.,basis=[1.,0.,0.,-1.],algorithm='color',parameters={}),
        dict(actor_id='A2',controller=2,lag_distance=25.,basis=[1.,0.,0.,-1.],algorithm='color',parameters={})])
    chains: list = field(default_factory=list)
    shortcuts: dict = field(default_factory=lambda:{'F10':'follow.pause','F11':'follow.resume'})
    record: bool = False

    def validate(self, *, for_start=False):
        if self.role not in ('A','B') or self.reference_walls not in ('base','active'):
            raise ValueError('角色或定位参考墙选择无效')
        if len(self.roi)!=4 or not all(isinstance(v,int) for v in self.roi) or not all(16<=v<=2048 for v in self.roi[2:]):
            raise ValueError('小地图宽高必须在16–2048像素内')
        if len(self.initial_origin)!=2 or not all(isfinite(v) for v in self.initial_origin):
            raise ValueError('初始定位坐标无效')
        if not 0<=self.search_radius<=1000 or not isfinite(self.scale) or not .1<=self.scale<=10:
            raise ValueError('定位搜索范围或比例无效')
        if not 20<=self.period_ms<=200 or not 50<=self.position_ttl_ms<=500 or not 0<=self.clearance<=20:
            raise ValueError('采样周期、坐标有效期或安全距离无效')
        if not 1<=len(self.actors)<= (2 if self.role=='A' else 1):
            raise ValueError('A端最多两个角色，B端一个角色')
        ids = [a['actor_id'] for a in self.actors]
        if len(set(ids))!=len(ids) or any(not a or len(a)>64 for a in ids):
            raise ValueError('角色标识必须唯一且非空')
        slots = [a['controller'] for a in self.actors]
        if self.role=='A' and (len(set(slots))!=len(slots) or any(s not in (1,2) for s in slots)):
            raise ValueError('角色必须分别绑定手柄1或2')
        for a in self.actors:
            if a['algorithm'] not in ('color','template') or not 0<=float(a['lag_distance'])<=1000:
                raise ValueError('角色识别算法或跟随距离无效')
            basis=a['basis']
            if len(basis)!=4 or not all(isfinite(v) for v in basis) or abs(basis[0]*basis[3]-basis[1]*basis[2])<1e-9:
                raise ValueError('地图到摇杆的方向变换不可用')
            if for_start and not a['parameters']:
                raise ValueError(f"请先配置 {a['actor_id']} 的颜色范围或ID模板，不能使用全颜色匹配")
            if for_start and a['algorithm']=='color':
                p=a['parameters']
                restrictive=any(p.get(key,default)!=default for key,default in (
                    ('hue_min',0),('hue_max',179),('saturation_min',0),('saturation_max',255),('value_min',0),('value_max',255)))
                if not restrictive or not 0<float(p.get('max_area',0))<self.roi[2]*self.roi[3]*.1:
                    raise ValueError('角色颜色必须限定HSV范围和最大面积，避免把整个小地图当成人物')
        if len(self.event_targets)!=len(set(self.event_targets)) or not 1<=len(self.event_targets)<=8 or any(not t or len(t)>64 for t in self.event_targets):
            raise ValueError('接收事件的角色标识必须非空且唯一')
        if for_start and len(self.actors)>1 and len({json.dumps((a['algorithm'],a['parameters']),sort_keys=True) for a in self.actors})!=len(self.actors):
            raise ValueError('两个角色不能使用完全相同的识别条件')
        from core.events.follow_chain import FollowChainDefinition
        names=set()
        for chain in self.chains:
            name=chain['name']
            if name in names or name.startswith('follow.'):
                raise ValueError('事件名称重复或使用了保留名称')
            names.add(name)
            FollowChainDefinition(name,chain['steps'],timeout_ms=chain.get('timeout_ms',30000),
                priority=chain.get('priority',0),resume=chain.get('resume',False))
        if any(key not in ('F1','F2','F3','F4','F5','F6','F10','F11','F12') for key in self.shortcuts):
            raise ValueError('F7/F8/F9保留给手柄暂停与急停，请为事件选择其他功能键')
        if for_start:
            if not Path(self.map_path).is_file() or not self.map_id or len(self.map_id)>64:
                raise ValueError('请选择地图文件并填写双方一致的地图标识')
            if self.role=='A' and not self.leader_device:
                raise ValueError('请选择已配对的B端设备')
        return self

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**deepcopy(data)).validate()


class FollowConfigStore:
    def __init__(self, root): self.root=Path(root)
    def versions(self): return sorted(self.root.glob('version-*.json'),reverse=True)
    def load(self, version=None):
        path=Path(version) if version else self.root/'active.json'
        return FollowConfig.from_dict(json.loads(path.read_text(encoding='utf-8'))) if path.exists() else FollowConfig()
    def save(self, config):
        config.validate()
        self.root.mkdir(parents=True,exist_ok=True)
        payload=json.dumps(config.to_dict(),ensure_ascii=False,indent=2,allow_nan=False)
        version=self.root/f"version-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}.json"
        version.write_text(payload,encoding='utf-8')
        temporary=self.root/f'.active-{uuid4().hex}.tmp'
        temporary.write_text(payload,encoding='utf-8')
        temporary.replace(self.root/'active.json')
        return version

"""Bounded, opt-in follow recording and device-free replay utilities."""
from pathlib import Path
from uuid import uuid4
import json
import time
import numpy as np


class FollowRecorder:
    def __init__(self, directory, *, max_records=1000):
        self.root=Path(directory)
        self.root.mkdir(parents=True,exist_ok=True)
        self.prefix=uuid4().hex
        self.limit=max_records
        self.count=0

    def record(self, kind, metadata, *, image=None, walls=None):
        if self.count>=self.limit:return False
        self.count+=1
        stem=f'{self.prefix}-{self.count:06d}'
        entry=dict(kind=kind,metadata=metadata)
        if image is not None or walls is not None:
            arrays={k:v for k,v in [('image',image),('walls',walls)] if v is not None}
            np.savez_compressed(self.root/f'{stem}.npz',**arrays)
            entry['arrays']=f'{stem}.npz'
        (self.root/f'{stem}.json').write_text(json.dumps(entry,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        return True


def replay_localization(directory, localizer):
    """Replay raw captured wall/marker frames. Does not import a device adapter."""
    from core.perception.models import FrameContext,CoordinateSpace
    records=[]
    root=Path(directory).resolve()
    for path in root.glob('*.json'):
        record=json.loads(path.read_text(encoding='utf-8'))
        if record.get('kind')=='vision':records.append(record)
    results=[]
    for record in sorted(records,key=lambda r:r['metadata']['captured_at_ms']):
        file=(root/record['arrays']).resolve()
        if file.parent!=root:raise ValueError('recording arrays must stay within replay directory')
        with np.load(file,allow_pickle=False) as data:
            image,walls=data['image'],data['walls']
        stamp=record['metadata']['captured_at_ms']
        frame=FrameContext(image,captured_at_ms=stamp,coordinate_space=CoordinateSpace.MINIMAP)
        started=time.perf_counter()
        snapshot=localizer.update(frame,walls,now_ms=stamp)
        results.append(dict(captured_at_ms=stamp,elapsed_ms=(time.perf_counter()-started)*1000,
            valid=snapshot.registration.valid,positions={k:v.position for k,v in snapshot.positions.items()}))
    return results


def summarize_timings(values):
    samples=np.asarray(values,dtype=float)
    if samples.size==0:return {'count':0}
    return dict(count=len(samples),median_ms=float(np.median(samples)),p95_ms=float(np.percentile(samples,95)),max_ms=float(samples.max()))

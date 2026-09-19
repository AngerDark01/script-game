"""Synthetic repeatable benchmark. Never captures the screen or drives a device.

Run: python -m auto_modules.features.torchlight.follow.benchmark
Results characterize this workload only, not real-game accuracy or LAN latency.
"""
import json
import time
import cv2
import numpy as np
from auto_modules.core.localization.map_runtime import MapRuntime
from auto_modules.core.localization.local_matcher import LocalMapMatcher
from auto_modules.core.localization.marker_detector import MarkerSetDetector
from auto_modules.core.localization.dual_localizer import MultiMarkerLocalizer
from auto_modules.core.perception.algorithms.color import ColorRegionDetector
from auto_modules.core.perception.models import FrameContext,CoordinateSpace
from auto_modules.features.torchlight.follow.planner import FollowerPlanner
from auto_modules.features.torchlight.follow.replay import summarize_timings


def run(samples=40):
    cv2.setNumThreads(1)
    rng=np.random.default_rng(20260911)
    walls=np.zeros((1024,1024),np.uint8)
    for _ in range(150):
        x,y=rng.integers(10,990,2)
        cv2.rectangle(walls,(int(x),int(y)),(int(x)+10,int(y)+12),255,1)
    runtime=MapRuntime.from_wall_layer(walls)
    markers=MarkerSetDetector({'A1':ColorRegionDetector('a1',dict(hue_min=40,hue_max=80,min_area=5,max_area=100)),
        'A2':ColorRegionDetector('a2',dict(hue_min=0,hue_max=10,saturation_min=100,min_area=5,max_area=100))})
    localizer=MultiMarkerLocalizer(LocalMapMatcher(runtime),markers,initial_origin=(210,200),search_radius=80)
    timings=[];errors=[]
    for i in range(samples):
        origin=(200+i,200+i//2)
        mask=walls[origin[1]:origin[1]+180,origin[0]:origin[0]+180]
        frame=cv2.cvtColor(mask,cv2.COLOR_GRAY2BGR)
        cv2.circle(frame,(60,80),4,(0,255,0),-1);cv2.circle(frame,(100,90),4,(0,0,255),-1)
        started=time.perf_counter()
        result=localizer.update(FrameContext(frame,captured_at_ms=i*50,coordinate_space=CoordinateSpace.MINIMAP),mask,now_ms=i*50)
        timings.append((time.perf_counter()-started)*1000)
        if result.registration.valid:
            errors.append(float(np.linalg.norm(np.array(result.registration.frame_origin_global)-origin)))
    nav=np.zeros((1024,1024),np.uint8); nav[100:900,500:505]=255
    planner=FollowerPlanner(nav)
    initial=[];cached=[]
    for i in range(5):
        started=time.perf_counter();path=planner.plan((100,400+i),(900,400),force=True);initial.append((time.perf_counter()-started)*1000)
        if not path:raise RuntimeError('benchmark route was not found')
        started=time.perf_counter();planner.plan((100,400+i),(900,400));cached.append((time.perf_counter()-started)*1000)
    return dict(workload='synthetic 1024x1024 map, 180x180 minimap, bounded radius80; no game input',
        localization=summarize_timings(timings),localized_frames=len(errors),samples=samples,
        maximum_origin_error_px=max(errors) if errors else None,
        full_replan=summarize_timings(initial),cached_plan=summarize_timings(cached))


if __name__=='__main__': print(json.dumps(run(),indent=2))

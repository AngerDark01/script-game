"""One vision process plus one planning/control process per local actor.

Only latest positions cross process boundaries. Events use bounded ordered
queues. Host output expiry is independent of every worker's responsiveness.
"""
import multiprocessing as mp
from queue import Empty, Full
import time
from uuid import uuid4


def clock_ms(): return int(time.monotonic()*1000)


def put_latest(queue, item):
    try: queue.put_nowait(item); return
    except Full: pass
    try: queue.get_nowait()
    except Empty: pass
    try: queue.put_nowait(item)
    except Full: pass


def latest(queue, previous=None):
    while True:
        try: previous=queue.get_nowait()
        except Empty: return previous


def parent_alive():
    parent=mp.parent_process()
    return parent is None or parent.is_alive()


def vision_worker(config, stop, frames, status, recording_dir=None):
    capture=None
    try:
        import cv2
        cv2.setNumThreads(1)
        from auto_modules.application.follow.resources import load_follow_maps
        from auto_modules.adapters.platform.screen_capture import SquareScreenCapture
        from auto_modules.core.vision.hsv_recognizer import HSVRecognizer
        from auto_modules.core.localization.local_matcher import LocalMapMatcher
        from auto_modules.core.localization.marker_detector import MarkerSetDetector
        from auto_modules.core.localization.dual_localizer import MultiMarkerLocalizer
        from auto_modules.core.perception.builtins import create_default_algorithm_registry
        from auto_modules.core.perception.models import FrameContext, CoordinateSpace
        from auto_modules.core.lan_follow import SharedPosition
        reference,_=load_follow_maps(config)
        registry=create_default_algorithm_registry()
        markers=MarkerSetDetector({a['actor_id']:registry.create(a['algorithm'],a['parameters']) for a in config.actors})
        localizer=MultiMarkerLocalizer(LocalMapMatcher(reference),markers,initial_origin=config.initial_origin,
            search_radius=config.search_radius,scale=config.scale,ttl_ms=config.position_ttl_ms)
        recognizer=HSVRecognizer()
        recognizer.set_params(config.recognizer)
        capture=SquareScreenCapture()
        from auto_modules.core.diagnostics.follow_replay import FollowRecorder
        recorder=FollowRecorder(recording_dir) if recording_dir else None
        session=uuid4().hex
        while not stop.is_set() and parent_alive():
            started=clock_ms()
            raw=capture.capture(*config.roi)
            frame=FrameContext(raw,captured_at_ms=started,coordinate_space=CoordinateSpace.MINIMAP)
            walls=recognizer.extract_walls(raw)
            snapshot=localizer.update(frame,walls,now_ms=clock_ms())
            positions={identity:SharedPosition('local',identity,config.map_id,reference.map_version,p.position,p.confidence,started,session)
                for identity,p in snapshot.positions.items() if p.position is not None}
            finished=clock_ms()
            if recorder:
                recorder.record('vision',dict(captured_at_ms=started,positions={a:p.position for a,p in positions.items()},
                    map_version=reference.map_version,elapsed_ms=finished-started),image=raw,walls=walls)
            put_latest(frames,positions)
            put_latest(status,dict(worker='vision',positions={a:p.position for a,p in positions.items()},
                localization_ms=finished-started,registration=snapshot.registration.valid,
                origin=snapshot.registration.frame_origin_global,map_version=reference.map_version))
            stop.wait(max(0,(config.period_ms-(finished-started))/1000))
    except Exception as exc:
        put_latest(status,dict(worker='vision',error=str(exc)))
    finally:
        if capture is not None: capture.close()


def actor_worker(config, actor, stop, observations, commands, status, recording_dir=None, client_factory=None):
    client=None; session=None
    identity=actor['actor_id']
    try:
        import cv2
        cv2.setNumThreads(1)
        from auto_modules.application.follow.resources import load_follow_maps
        from auto_modules.application.follow.controller import FollowerController
        from auto_modules.application.follow.dual_session import DualFollowSession
        from auto_modules.adapters.virtual_gamepad import ProgramGamepadOutput
        from auto_modules.core.events.registry import EventRegistry
        from auto_modules.core.events.follow_chain import FollowChainDefinition
        from auto_modules.core.events.hooks.registry import EventHookRegistry
        from auto_modules.core.events.session import EventSession
        from auto_modules.core.events.action_tracks import ActionTrack, TrackMode
        from auto_modules.core.events.follow_chain import BUTTONS
        from auto_modules.adapters.virtual_gamepad import VirtualGamepadClient
        reference,nav=load_follow_maps(config)
        controller=FollowerController(nav,actor_id=identity,map_id=config.map_id,map_version=reference.map_version,
            lag_distance=actor['lag_distance'],ttl_ms=config.position_ttl_ms)
        client=(client_factory or VirtualGamepadClient)(); client.connect(timeout=2)
        output=ProgramGamepadOutput(client,controller=actor['controller'],basis=actor['basis'])
        registry=EventRegistry(); hooks=EventHookRegistry()
        for chain in config.chains:
            if not chain.get('enabled',True): continue
            registry.register(FollowChainDefinition(chain['name'],chain['steps'],hooks=hooks,
                priority=chain.get('priority',0),timeout_ms=chain.get('timeout_ms',30000),resume=chain.get('resume',False)))
        session=DualFollowSession({identity:controller},{identity:output},event_registry=registry,
            leader_device=config.leader_device,leader_actor=config.leader_actor,clock_ms=clock_ms)
        # New timed track definitions are optional and coexist with legacy chains.
        track_definitions={}
        for item in config.chains:
            tracks=[]
            for raw in item.get('tracks', []):
                tracks.append(ActionTrack(tuple(raw['buttons']), mode=TrackMode(raw.get('mode','once')),
                    hold_ms=int(raw.get('hold_ms',100)), interval_ms=raw.get('interval_ms'), end_ms=raw.get('end_ms')))
            if tracks:
                from types import SimpleNamespace
                track_definitions[item['name']]=SimpleNamespace(tracks=tuple(tracks),
                    max_runs=item.get('max_runs'), loop=bool(item.get('loop',False)), end_ms=item.get('end_ms'))
        event_session=EventSession(track_definitions,clock_ms=clock_ms)
        from auto_modules.core.diagnostics.follow_replay import FollowRecorder
        recorder=FollowRecorder(recording_dir) if recording_dir else None
        observed=({},()); last_status=0
        while not stop.is_set() and parent_alive():
            started=clock_ms()
            for _ in range(32):
                try: command=commands.get_nowait()
                except Empty: break
                if command['kind']=='start':
                    if not session.armed[identity]:
                        try: session.start(identity,requested_at_ms=command['requested_at_ms'])
                        except Exception as exc: session.errors[identity]=str(exc)
                elif command['kind']=='stop':
                    try: session.stop(identity)
                    except Exception as exc: session.errors[identity]=str(exc)
                elif command['kind']=='event':
                    event = command['event']
                    if event.name in track_definitions:
                        event_session.receive_remote(event)
                    else:
                        session.receive(event)
                if recorder: recorder.record('control_event',dict(actor=identity,kind=command['kind'],at_ms=clock_ms(),event=str(command.get('event',''))))
            observed=latest(observations,observed)
            event_buttons = 0
            for name in event_session.tick():
                event_buttons |= BUTTONS.get(name, 0)
            session.tick(*observed, button_overrides={identity: event_buttons})
            if clock_ms()-last_status>=100:
                decision=session.decisions.get(identity)
                put_latest(status,dict(worker=identity,mode=session.mode[identity],armed=session.armed[identity],
                    state=decision.state if decision else 'paused',path=decision.path if decision else (),
                    vector=decision.vector if decision else (0,0),error=session.errors.get(identity,''),
                    planning_ms=clock_ms()-started))
                if recorder: recorder.record('decision',dict(actor=identity,at_ms=clock_ms(),
                    mode=session.mode[identity],path=decision.path if decision else (),vector=decision.vector if decision else (0,0)))
                last_status=clock_ms()
            stop.wait(max(0,(20-(clock_ms()-started))/1000))
    except Exception as exc:
        put_latest(status,dict(worker=identity,error=str(exc),armed=False))
    finally:
        if session is not None: session.close()
        if client is not None: client.close()

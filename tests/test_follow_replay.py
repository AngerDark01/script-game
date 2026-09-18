import numpy as np
from auto_modules.core.diagnostics.follow_replay import FollowRecorder,replay_localization,summarize_timings
from auto_modules.core.localization.dual_localizer import LocalizationSnapshot
from auto_modules.core.shared.frame_registration import FrameRegistration


def test_record_replay_preserves_frame_timestamp_and_bounds_disk_output(tmp_path):
    recorder=FollowRecorder(tmp_path,max_records=2)
    assert recorder.record('vision',{'captured_at_ms':100},image=np.zeros((20,20,3),np.uint8),walls=np.zeros((20,20),np.uint8))
    assert recorder.record('decision',{'actor':'A1','vector':[0,0]})
    assert not recorder.record('decision',{})
    class Localizer:
        def update(self,frame,walls,now_ms):
            assert frame.captured_at_ms==now_ms==100
            return LocalizationSnapshot(now_ms,FrameRegistration(True),{})
    result=replay_localization(tmp_path,Localizer())
    assert len(result)==1 and result[0]['valid']
    assert summarize_timings([1,2,3])['median_ms']==2

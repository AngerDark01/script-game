from core.lan_follow.follow_transport import FollowTransport


def test_poll_counts_ipc_delay_and_discards_expired_events():
    now = [1000]
    class Client:
        def request(self, kind):
            now[0] += 80
            return {'status': {'sharedPositions': [dict(deviceId='B', sessionId='s', ageMs=100,
                position=dict(actorId='B', mapId='map', mapVersion='v1', x=1, y=2, confidence=.9))]},
                'events': [dict(deviceId='B', sessionId='s', id='e', name='return', targets=['A1'], remainingMs=50)]}
    positions, events = FollowTransport(Client(), clock_ms=lambda: now[0]).poll()
    assert positions[0].captured_at_ms == 900
    assert now[0]-positions[0].captured_at_ms == 180
    assert not events


def test_outbound_expired_intent_never_contacts_host():
    class Client:
        def request(self,*args):raise AssertionError('expired event must be dropped')
    assert FollowTransport(Client()).send_event('B','return',['A1'],host_deadline_ms=0) is False

"""Direct sender for remote events; does not start localization or follow workers."""
from __future__ import annotations

from core.actions.program_gamepad import host_clock_ms

class RemoteEventSender:
    def __init__(self, client_factory=None):
        self.client_factory = client_factory

    def send(self, device_id: str, event_name: str, controller: str = 'Controller 1'):
        if not device_id.strip(): raise ValueError('remote device id is required')
        if not event_name.strip(): raise ValueError('event name is required')
        targets = ['1', '2'] if controller == 'Controller 1 + 2' else ['2'] if controller == 'Controller 2' else ['1']
        from virtual_gamepad.client.python import VirtualGamepadClient
        client = (self.client_factory or VirtualGamepadClient)(); client.connect(timeout=2)
        try:
            status = client.request('sync.status').get('status', {})
            peer = next(
                (item for item in status.get('peers', [])
                 if str(item.get('deviceId', '')).strip() == device_id.strip()),
                None,
            )
            if peer is None or not peer.get('connected') or not peer.get('syncing') or not peer.get('dataOnly'):
                raise RuntimeError('target has no connected shared-event session')
            # LanSyncService validates deadlines against .NET TickCount64 and
            # accepts at most 500 ms.  Use the same host clock as program
            # gamepad output; Python's monotonic clock is not a wire contract.
            return client.request('sync.share.event', {
                'deviceId': device_id.strip(),
                'name': event_name.strip(),
                'targets': targets,
                'deadlineMs': host_clock_ms() + 250,
            })
        finally:
            client.close()

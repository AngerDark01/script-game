"""Direct sender for remote events; does not start localization or follow workers."""
from __future__ import annotations
import time

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
            return client.request('sync.share.event', {'deviceId': device_id.strip(), 'name': event_name.strip(), 'targets': targets, 'deadlineMs': int(time.monotonic()*1000)+1000})
        finally:
            client.close()

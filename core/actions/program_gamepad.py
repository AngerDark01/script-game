"""Exclusive program output using the existing virtual-gamepad host/client.

Acquisition is explicit; writes cannot arm or re-arm a revoked controller. The
host owns the short output timeout so Python/vision stalls cannot hold a stick.
"""
from math import hypot, isfinite
from .gamepad_motion import StickSlewLimiter
import os
import time


def host_clock_ms():
    """Same-machine Windows uptime, identical to .NET Environment.TickCount64."""
    if os.name == 'nt':
        import ctypes
        get_ticks = ctypes.windll.kernel32.GetTickCount64
        get_ticks.restype = ctypes.c_ulonglong
        return get_ticks()
    return int(time.monotonic()*1000)


class ProgramGamepadOutput:
    def __init__(self, client, *, controller, basis=(1., 0., 0., -1.), ttl_ms=120):
        if controller not in (1, 2) or not 1 <= ttl_ms <= 300:
            raise ValueError('invalid controller or TTL')
        if len(basis) != 4 or not all(isfinite(v) for v in basis) or abs(basis[0]*basis[3]-basis[1]*basis[2]) < 1e-9:
            raise ValueError('non-singular finite map-to-stick basis required')
        self.client, self.controller, self.basis, self.ttl_ms = client, controller, basis, ttl_ms
        self.token = None
        self.limiter = StickSlewLimiter()

    def start(self, *, requested_at_ms=None):
        if self.token is not None:
            raise RuntimeError('program output is already acquired')
        self.token = self.client.request('program.acquire', {'controller': self.controller,
            'requestedAtMs': host_clock_ms() if requested_at_ms is None else requested_at_ms})['token']
        self.limiter.reset()

    def write(self, vector, *, elapsed_ms=20, valid_for_ms=None, buttons=0):
        if self.token is None:
            raise RuntimeError('program output is not acquired')
        if len(vector) != 2 or not all(isfinite(v) for v in vector):
            raise ValueError('finite movement vector required')
        a, b, c, d = self.basis
        x, y = a*vector[0]+b*vector[1], c*vector[0]+d*vector[1]
        norm = max(1., hypot(x, y))
        if x == y == 0:
            axes = self.limiter.reset()  # safety stops must not slew
        else:
            axes = self.limiter.update(round(x/norm*32767), round(y/norm*32767), elapsed_ms=min(50, max(0, int(elapsed_ms))))
        ttl = self.ttl_ms if valid_for_ms is None else min(self.ttl_ms, int(valid_for_ms))
        if ttl <= 0:
            axes, buttons, ttl = self.limiter.reset(), 0, self.ttl_ms
        self.client.request('program.state', dict(controller=self.controller, token=self.token, ttlMs=ttl, deadlineMs=host_clock_ms()+ttl,
            state=dict(buttons=buttons, leftTrigger=0, rightTrigger=0,
                       leftStickX=axes[0], leftStickY=axes[1], rightStickX=0, rightStickY=0)))

    def stop(self):
        token, self.token = self.token, None
        self.limiter.reset()
        if token is not None:
            self.client.request('program.release', dict(controller=self.controller, token=token))

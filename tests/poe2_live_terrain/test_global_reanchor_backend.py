from auto_modules.features.poe2.live_terrain.experimental.multiplayer_follow.recovery.global_reanchor import (
    GlobalReanchorBackend,
)


def test_global_backend_is_the_only_side_effect_adapter():
    calls = []
    backend = GlobalReanchorBackend(lambda **kwargs: calls.append(kwargs))

    request = backend.start("memory_failed", preserve_follow=True)

    assert request.reason == "memory_failed"
    assert request.preserve_follow is True
    assert backend.started == 1
    assert calls == [{"recovery": True, "preserve_follow": True}]


def test_global_backend_keeps_static_legacy_call_shape():
    calls = []
    backend = GlobalReanchorBackend(lambda **kwargs: calls.append(kwargs))

    backend.start("static_retry", preserve_follow=False)

    assert calls == [{"recovery": True}]

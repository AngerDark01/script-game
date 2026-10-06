from auto_modules.features.poe2.live_terrain.experimental.localization.service import (
    PositionEstimate,
    RelocalizationService,
)


class _Relocalizer:
    def locate(self, context):
        return PositionEstimate((1, 2), "first_frame", 0.9, fresh=True)


def test_relocalization_service_keeps_last_estimate_and_can_invalidate():
    service = RelocalizationService(_Relocalizer())
    estimate = service.locate({})
    assert service.last_estimate is estimate
    service.invalidate("map_changed")
    assert service.last_estimate.fresh is False

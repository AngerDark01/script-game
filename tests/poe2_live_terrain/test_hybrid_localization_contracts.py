from auto_modules.features.poe2.live_terrain.experimental.hybrid_localization.contracts import (
    AbsoluteRegistrar,
    AnchorProvider,
    LocalTracker,
)


class AnchorFake:
    def read_once(self, expected_instance_id):
        return None


class RegistrarFake:
    last_diagnostics = {}

    def register(self, frame, *, reference, anchor, prior=None):
        return None


class TrackerFake:
    def track(self, frame, *, reference, previous_frame, previous):
        return None


def test_contracts_accept_structural_implementations():
    assert isinstance(AnchorFake(), AnchorProvider)
    assert isinstance(RegistrarFake(), AbsoluteRegistrar)
    assert isinstance(TrackerFake(), LocalTracker)

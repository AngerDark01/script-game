"""Identity-keyed composition of existing color/template perception detectors."""
from core.perception.models import CoordinateSpace


class MarkerSetDetector:
    def __init__(self, detectors, *, min_confidence=0.5):
        if not detectors or not 0 <= min_confidence <= 1:
            raise ValueError('detectors and valid confidence threshold required')
        self.detectors = dict(detectors)
        self.min_confidence = min_confidence

    def detect(self, frame):
        if frame.coordinate_space != CoordinateSpace.MINIMAP:
            raise ValueError('marker detection requires minimap coordinates')
        result = {}
        for identity, detector in self.detectors.items():
            matches = [m for m in detector.detect(frame)
                       if m.confidence >= self.min_confidence
                       and m.coordinate_space == CoordinateSpace.MINIMAP]
            # Never infer identity from contour ordering. Ambiguity is a missing
            # observation, not permission to drive another player's controller.
            result[identity] = matches[0] if len(matches) == 1 else None
        return result

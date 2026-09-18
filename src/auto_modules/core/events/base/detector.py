from __future__ import annotations

from abc import ABC, abstractmethod


class EventDetector(ABC):
    event_type: str = ""

    @abstractmethod
    def detect(self, tick, config) -> list:
        raise NotImplementedError


from __future__ import annotations

from abc import ABC, abstractmethod


class EventHandler(ABC):
    event_type: str = ""

    def start(self, task) -> None:
        self.task = task

    @abstractmethod
    def update(self, tick, task):
        raise NotImplementedError

    def reset(self) -> None:
        self.task = None


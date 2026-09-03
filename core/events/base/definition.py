from __future__ import annotations

from abc import ABC, abstractmethod


class EventDefinition(ABC):
    event_type: str = ""
    display_name: str = ""
    description: str = ""

    @abstractmethod
    def default_config(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def config_schema(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def create_detector(self, config):
        raise NotImplementedError

    @abstractmethod
    def create_handler(self, config):
        raise NotImplementedError


from __future__ import annotations


class EventRegistry:
    def __init__(self):
        self._definitions = {}

    def register(self, definition):
        event_type = getattr(definition, "event_type", "")
        if not event_type:
            raise ValueError("event definition missing event_type")
        if event_type in self._definitions:
            raise ValueError(f"duplicate event definition: {event_type}")
        self._definitions[event_type] = definition
        return definition

    def get(self, event_type: str):
        return self._definitions.get(event_type)

    def definitions(self) -> list:
        return list(self._definitions.values())

    def enabled_definitions(self, config) -> list:
        result = []
        for definition in self.definitions():
            event_config = config.event(definition.event_type) if hasattr(config, "event") else {}
            if event_config.get("enabled", True):
                result.append(definition)
        return result


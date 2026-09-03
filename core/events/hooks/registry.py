from __future__ import annotations

from collections.abc import Callable

from core.events.debug import event_log

from .models import EventHookContext


EventHookHandler = Callable[[EventHookContext], None]


class EventHookRegistry:
    """Small synchronous hook registry for event lifecycle extension points."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHookHandler]] = {}

    def register(self, hook_name: str, handler: EventHookHandler) -> Callable[[], None]:
        name = _normalize_hook_name(hook_name)
        if not callable(handler):
            raise TypeError("event hook handler must be callable")
        self._handlers.setdefault(name, []).append(handler)
        return lambda: self.unregister(name, handler)

    def unregister(self, hook_name: str, handler: EventHookHandler) -> bool:
        name = _normalize_hook_name(hook_name)
        handlers = self._handlers.get(name)
        if not handlers:
            return False
        try:
            handlers.remove(handler)
        except ValueError:
            return False
        if not handlers:
            self._handlers.pop(name, None)
        return True

    def clear(self, hook_name: str | None = None) -> None:
        if hook_name is None:
            self._handlers.clear()
            return
        self._handlers.pop(_normalize_hook_name(hook_name), None)

    def handlers(self, hook_name: str) -> tuple[EventHookHandler, ...]:
        return tuple(self._handlers.get(_normalize_hook_name(hook_name), ()))

    def emit(self, context: EventHookContext) -> int:
        handlers = self.handlers(context.hook_name)
        for handler in handlers:
            try:
                handler(context)
            except Exception as exc:
                event_log(
                    "event hook handler failed",
                    hook=context.hook_name,
                    handler=_handler_name(handler),
                    error=repr(exc),
                )
        return len(handlers)


def _normalize_hook_name(hook_name: str) -> str:
    name = str(hook_name or "").strip()
    if not name:
        raise ValueError("event hook name cannot be empty")
    return name


def _handler_name(handler: EventHookHandler) -> str:
    return getattr(handler, "__qualname__", getattr(handler, "__name__", handler.__class__.__name__))


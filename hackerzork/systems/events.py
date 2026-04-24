"""Event bus — decoupled inter-system communication."""
from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class Event:
    name: str
    data: dict
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"name": self.name, "data": self.data, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, d: dict) -> Event:
        return cls(name=d["name"], data=d["data"], timestamp=d["timestamp"])


class EventBus:
    def __init__(self, max_history: int = 1000) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history = max_history

    def on(self, event_name: str, handler: Callable) -> None:
        """Register a handler for an event."""
        if handler not in self._handlers[event_name]:
            self._handlers[event_name].append(handler)

    def off(self, event_name: str, handler: Callable) -> None:
        """Unregister a handler."""
        try:
            self._handlers[event_name].remove(handler)
        except ValueError:
            pass

    def emit(self, event_name: str, **data) -> None:
        """Emit an event synchronously to all registered handlers."""
        event = self._record(event_name, data)
        for handler in list(self._handlers.get(event_name, [])):
            self._call_safe(handler, event)

    async def emit_async(self, event_name: str, **data) -> None:
        """Emit an event; awaits coroutine handlers, calls sync handlers normally."""
        event = self._record(event_name, data)
        for handler in list(self._handlers.get(event_name, [])):
            if inspect.iscoroutinefunction(handler):
                try:
                    await handler(event)
                except Exception:
                    logger.exception("Async handler %r raised on event %r", handler, event_name)
            else:
                self._call_safe(handler, event)

    def history(self, event_name: str | None = None) -> list[Event]:
        """Return event history, optionally filtered by name."""
        if event_name is None:
            return list(self._history)
        return [e for e in self._history if e.name == event_name]

    def clear_history(self) -> None:
        self._history.clear()

    def _record(self, event_name: str, data: dict) -> Event:
        event = Event(name=event_name, data=data)
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        return event

    def _call_safe(self, handler: Callable, event: Event) -> None:
        try:
            handler(event)
        except Exception:
            logger.exception("Handler %r raised on event %r", handler, event.name)

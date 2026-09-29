"""Small bounded sliding-window limiter for the single-process demo API."""

from __future__ import annotations

from collections import OrderedDict


class SlidingWindowRateLimiter:
    def __init__(self, *, requests: int, window_seconds: float, max_clients: int) -> None:
        if requests < 1 or window_seconds <= 0 or max_clients < 1:
            raise ValueError("Rate-limit settings must be positive.")
        self.requests = requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._events: OrderedDict[str, list[float]] = OrderedDict()

    def allow(self, client_key: str, now: float) -> bool:
        cutoff = now - self.window_seconds
        for key, timestamps in list(self._events.items()):
            retained = [stamp for stamp in timestamps if stamp > cutoff]
            if retained:
                self._events[key] = retained
            else:
                del self._events[key]

        timestamps = self._events.pop(client_key, [])
        if len(timestamps) >= self.requests:
            self._events[client_key] = timestamps
            return False

        if len(self._events) >= self.max_clients:
            self._events.popitem(last=False)
        timestamps.append(now)
        self._events[client_key] = timestamps
        return True

    @property
    def tracked_clients(self) -> int:
        return len(self._events)

"""Bounded-window latency and throughput metrics."""
from __future__ import annotations

import time
from collections import deque
from math import ceil, isfinite


class LatencyMonitor:
    def __init__(self, sample_size: int = 10_000, window_seconds: float = 1.0) -> None:
        if (
            isinstance(sample_size, bool)
            or not isinstance(sample_size, int)
            or sample_size <= 0
        ):
            raise ValueError("sample_size must be a positive integer")
        try:
            window_is_finite = isfinite(window_seconds)
        except (OverflowError, TypeError):
            window_is_finite = False
        if (
            isinstance(window_seconds, bool)
            or not isinstance(window_seconds, (int, float))
            or not window_is_finite
            or window_seconds <= 0
        ):
            raise ValueError("window_seconds must be positive and finite")
        self.window_ns = int(window_seconds * 1_000_000_000)
        if self.window_ns == 0:
            raise ValueError("window_seconds is too small")
        self._samples: deque[tuple[int, int]] = deque(maxlen=sample_size)
        self._events: deque[int] = deque()
        self._observations = 0
        self._total_latency_ns = 0

    def record(self, started_ns: int, finished_ns: int) -> int:
        if (
            isinstance(started_ns, bool)
            or not isinstance(started_ns, int)
            or isinstance(finished_ns, bool)
            or not isinstance(finished_ns, int)
            or started_ns < 0
            or finished_ns < started_ns
        ):
            raise ValueError("timestamps must be non-negative and monotonic")
        latency_ns = finished_ns - started_ns
        self._samples.append((finished_ns, latency_ns))
        self._events.append(finished_ns)
        self._prune_events(finished_ns)
        self._observations += 1
        self._total_latency_ns += latency_ns
        return latency_ns

    def snapshot(self, now_ns: int | None = None) -> dict[str, float | int]:
        now = time.perf_counter_ns() if now_ns is None else now_ns
        if isinstance(now, bool) or not isinstance(now, int) or now < 0:
            raise ValueError("now_ns must be a non-negative integer")
        self._prune_events(now)
        samples = [latency for _, latency in self._samples]
        ordered = sorted(samples)
        p99_index = max(0, ceil(len(ordered) * 0.99) - 1)
        return {
            "samples": len(samples),
            "observations": self._observations,
            "latest_latency_us": samples[-1] / 1000 if samples else 0.0,
            "average_latency_us": (
                self._total_latency_ns / self._observations / 1000
                if self._observations
                else 0.0
            ),
            "p99_latency_us": ordered[p99_index] / 1000 if ordered else 0.0,
            "throughput_orders_per_second": (
                len(self._events) / (self.window_ns / 1_000_000_000)
            ),
        }

    def _prune_events(self, now_ns: int) -> None:
        cutoff = now_ns - self.window_ns
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

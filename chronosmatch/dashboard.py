"""Curses terminal dashboard with a separately testable text renderer."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable

from .matching_engine import Trade


def _validate_whale_threshold(whale_threshold: int) -> None:
    if (
        isinstance(whale_threshold, bool)
        or not isinstance(whale_threshold, int)
        or whale_threshold <= 0
    ):
        raise ValueError("whale_threshold must be a positive integer")


@dataclass(frozen=True, slots=True)
class DashboardState:
    bids: list[tuple[float, int]]
    asks: list[tuple[float, int]]
    spread: float | None
    latest_latency_us: float
    p99_latency_us: float
    throughput_orders_per_second: float
    recent_trades: list[Trade]
    engine_latency_us: float = 0.0
    engine_p99_latency_us: float = 0.0


def render_dashboard(
    state: DashboardState, whale_threshold: int = 1_000
) -> list[tuple[str, bool]]:
    """Render dashboard lines and indicate whether each line highlights a whale."""
    _validate_whale_threshold(whale_threshold)
    lines = [
        ("ChronosMatch | price-time matching | Ctrl-C to exit", False),
        (
            f"Spread: {state.spread if state.spread is not None else 'n/a'}"
            f" | Latest: {state.latest_latency_us:.2f} us"
            f" | p99: {state.p99_latency_us:.2f} us"
            f" | engine: {state.engine_latency_us:.2f} us"
            f" (p99 {state.engine_p99_latency_us:.2f} us)"
            f" | Throughput: {state.throughput_orders_per_second:.0f} orders/s",
            False,
        ),
        ("", False),
        ("BIDS (price, quantity)", False),
    ]
    lines.extend((f"  {price:.4f}  {quantity}", False) for price, quantity in state.bids)
    lines.extend([("", False), ("ASKS (price, quantity)", False)])
    lines.extend((f"  {price:.4f}  {quantity}", False) for price, quantity in state.asks)
    lines.extend([("", False), ("Recent trades", False)])
    for trade in state.recent_trades[-5:]:
        is_whale = trade.quantity >= whale_threshold
        label = " WHALE" if is_whale else ""
        lines.append(
            (
                f"  #{trade.trade_id} {trade.buy_order_id}/{trade.sell_order_id} "
                f"{trade.quantity} @ {trade.price:.4f}{label}",
                is_whale,
            )
        )
    return lines


def run_curses_dashboard(
    state_provider: Callable[[], DashboardState],
    *,
    refresh_seconds: float = 0.1,
    whale_threshold: int = 1_000,
) -> None:
    if (
        isinstance(refresh_seconds, bool)
        or not isinstance(refresh_seconds, (int, float))
        or not math.isfinite(refresh_seconds)
        or refresh_seconds <= 0
    ):
        raise ValueError("refresh_seconds must be a positive finite number")
    _validate_whale_threshold(whale_threshold)
    try:
        import curses
    except ImportError as exc:
        raise RuntimeError(
            "Curses dashboard support is unavailable. On Windows, install "
            "the optional dependency with: python -m pip install "
            "-r requirements-dashboard.txt"
        ) from exc

    def draw(screen) -> None:
        curses.curs_set(0)
        screen.timeout(max(1, int(refresh_seconds * 1000)))
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_YELLOW)
        while True:
            state = state_provider()
            screen.erase()
            height, width = screen.getmaxyx()
            for row, (line, is_whale) in enumerate(
                render_dashboard(state, whale_threshold)[: max(0, height - 1)]
            ):
                if width > 1:
                    if is_whale and curses.has_colors():
                        screen.addnstr(row, 0, line, width - 1, curses.color_pair(1))
                    else:
                        screen.addnstr(row, 0, line, width - 1)
            screen.refresh()
            if screen.getch() in (ord("q"), ord("Q")):
                return

    curses.wrapper(draw)

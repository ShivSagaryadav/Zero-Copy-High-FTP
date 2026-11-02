import sys
from types import SimpleNamespace

import pytest

from chronosmatch.dashboard import DashboardState, render_dashboard
from chronosmatch.dashboard import run_curses_dashboard
from chronosmatch import MatchingEngine, Order
from chronosmatch.matching_engine import Trade


def test_dashboard_formats_book_metrics_and_highlights_whale_trade():
    state = DashboardState(
        bids=[(99.5, 10)],
        asks=[(100.0, 20)],
        spread=0.5,
        latest_latency_us=12.5,
        p99_latency_us=20.0,
        throughput_orders_per_second=1000.0,
        recent_trades=[
            Trade(1, "B", "S", 100.0, 1500, 1.0, 1000),
        ],
    )
    lines = render_dashboard(state, whale_threshold=1000)
    trade_lines = [line for line, is_whale in lines if is_whale]
    assert len(trade_lines) == 1
    assert "WHALE" in trade_lines[0]
    assert any("Spread: 0.5" in line for line, _ in lines)


def test_curses_dashboard_refreshes_live_state_and_quits(monkeypatch):
    class Screen:
        def __init__(self):
            self.frames = []
            self.current = []
            self.key_reads = 0

        def timeout(self, _milliseconds):
            pass

        def erase(self):
            self.current = []

        def getmaxyx(self):
            return 20, 120

        def addnstr(self, _row, _column, text, _width):
            self.current.append(text)

        def refresh(self):
            self.frames.append(tuple(self.current))

        def getch(self):
            self.key_reads += 1
            return -1 if self.key_reads == 1 else ord("q")

    screen = Screen()
    curses = SimpleNamespace(
        curs_set=lambda _visibility: None,
        has_colors=lambda: False,
        wrapper=lambda draw: draw(screen),
    )
    monkeypatch.setitem(sys.modules, "curses", curses)
    states = iter(
        [
            DashboardState([], [], None, 1, 2, 3, []),
            DashboardState([], [], None, 4, 5, 6, []),
        ]
    )

    run_curses_dashboard(lambda: next(states))

    assert len(screen.frames) == 2
    assert any("Latest: 1.00 us" in line for line in screen.frames[0])
    assert any("Latest: 4.00 us" in line for line in screen.frames[1])


def test_dashboard_highlights_whale_order_split_across_price_levels():
    engine = MatchingEngine()
    engine.submit(Order("S1", "SELL", 100.0, 600))
    engine.submit(Order("S2", "SELL", 101.0, 600))
    trades = engine.submit(Order("B1", "BUY", 101.0, 1200))
    state = DashboardState([], [], None, 0, 0, 0, trades)

    whale_lines = [
        line for line, highlighted in render_dashboard(state, 1000) if highlighted
    ]

    assert [trade.quantity for trade in trades] == [600, 600]
    assert len(whale_lines) == 2
    assert all("order 1200" in line for line in whale_lines)


@pytest.mark.parametrize("threshold", [0, -1, 1.5, True])
def test_dashboard_rejects_invalid_whale_threshold(threshold):
    with pytest.raises(ValueError, match="whale_threshold"):
        render_dashboard(DashboardState([], [], None, 0, 0, 0, []), threshold)


@pytest.mark.parametrize("refresh_seconds", [0, -0.1, float("nan"), float("inf"), True])
def test_dashboard_rejects_invalid_refresh_interval_before_starting_curses(
    refresh_seconds,
):
    with pytest.raises(ValueError, match="refresh_seconds"):
        run_curses_dashboard(lambda: DashboardState([], [], None, 0, 0, 0, []),
                             refresh_seconds=refresh_seconds)

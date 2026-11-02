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

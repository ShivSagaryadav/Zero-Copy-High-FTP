from chronosmatch.dashboard import DashboardState, render_dashboard
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

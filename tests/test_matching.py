from array import array

import pytest

from chronosmatch import Order, OrderStatus, OrderType, MatchingEngine
from chronosmatch import _matcher
from chronosmatch._python_matcher import match_orders as python_match_orders


def test_exact_match():
    e = MatchingEngine()
    e.submit(Order("S", "SELL", 100.5, 10))
    t = e.submit(Order("B", "BUY", 100.5, 10))
    assert len(t) == 1 and t[0].quantity == 10 and t[0].value == 1005.0
    assert 0 <= t[0].latency_ns <= t[0].end_to_end_latency_ns
    assert len(e.book) == 0


def test_partial_fill_incoming_larger():
    e = MatchingEngine()
    e.submit(Order("S", "SELL", 100.5, 6))
    t = e.submit(Order("B", "BUY", 100.5, 10))
    assert t[0].quantity == 6
    assert e.book.best_bid().remaining == 4
    assert e.status("B") == OrderStatus.PARTIALLY_FILLED.value


def test_partial_fill_resting_larger():
    e = MatchingEngine()
    e.submit(Order("S", "SELL", 100, 10))
    e.submit(Order("B", "BUY", 100, 4))
    assert e.book.best_ask().remaining == 6
    assert e.status("S") == OrderStatus.PARTIALLY_FILLED.value
    assert e.status("B") == OrderStatus.FILLED.value


def test_no_match_when_prices_do_not_cross():
    e = MatchingEngine()
    e.submit(Order("S", "SELL", 101, 5))
    assert e.submit(Order("B", "BUY", 100, 5)) == []
    assert len(e.book) == 2


def test_price_time_priority():
    e = MatchingEngine()
    e.submit(Order("S1", "SELL", 100, 5))
    e.submit(Order("S2", "SELL", 100, 5))
    t = e.submit(Order("B", "BUY", 100, 5))
    assert t[0].sell_order_id == "S1"


def test_best_price_first_and_multi_level():
    e = MatchingEngine()
    e.submit(Order("S1", "SELL", 102, 5))
    e.submit(Order("S2", "SELL", 101, 5))
    t = e.submit(Order("B", "BUY", 102, 8))
    assert [(x.sell_order_id, x.price, x.quantity) for x in t] == \
        [("S2", 101, 5), ("S1", 102, 3)]


def test_sell_side_incoming_hits_best_bid():
    e = MatchingEngine()
    e.submit(Order("B1", "BUY", 99, 5))
    e.submit(Order("B2", "BUY", 100, 5))
    t = e.submit(Order("S", "SELL", 99, 7))
    assert [(x.buy_order_id, x.price, x.quantity) for x in t] == \
        [("B2", 100, 5), ("B1", 99, 2)]


def test_cancel():
    e = MatchingEngine()
    e.submit(Order("S", "SELL", 100, 5))
    assert e.cancel("S") is True
    assert e.submit(Order("B", "BUY", 100, 5)) == []
    assert e.status("S") == OrderStatus.CANCELLED.value


def test_market_buy_executes_best_prices_and_cancels_unfilled_remainder():
    e = MatchingEngine()
    e.submit(Order("S1", "SELL", 101, 2))
    e.submit(Order("S2", "SELL", 102, 3))

    trades = e.submit(
        Order("B", "BUY", None, 7, order_type=OrderType.MARKET)
    )

    assert [(trade.price, trade.quantity) for trade in trades] == [(101, 2), (102, 3)]
    assert e.status("B") == OrderStatus.PARTIALLY_FILLED.value
    assert e.book.get("B") is None
    assert e.book.best_ask() is None


def test_symbols_have_independent_books_and_trades():
    e = MatchingEngine()
    e.submit(Order("A-SELL", "SELL", 100, 2, symbol="AAPL"))
    assert e.submit(Order("B-BUY", "BUY", 100, 2, symbol="MSFT")) == []
    trades = e.submit(Order("A-BUY", "BUY", 100, 2, symbol="aapl"))

    assert len(trades) == 1
    assert trades[0].symbol == "AAPL"
    assert e.book_for("MSFT").best_bid().remaining == 2
    assert e.status("A-SELL") == OrderStatus.FILLED.value


def test_status_tracks_cancelled_filled_and_unknown_orders():
    e = MatchingEngine()
    e.submit(Order("S", "SELL", 100, 1))
    e.submit(Order("B", "BUY", 100, 1))
    e.submit(Order("C", "BUY", 99, 1))
    assert e.status("S") == OrderStatus.FILLED.value
    assert e.status("C") == OrderStatus.OPEN.value
    assert e.cancel("C")
    assert e.status("C") == OrderStatus.CANCELLED.value
    assert e.status("missing") == "UNKNOWN"


@pytest.mark.skipif(
    _matcher._cython_match_orders is None,
    reason="optional Cython extension is not built",
)
def test_python_and_cython_engines_produce_identical_results(monkeypatch):
    def replay(kernel):
        monkeypatch.setattr(_matcher, "match_orders", kernel)
        engine = MatchingEngine()
        orders = [
            Order("S1", "SELL", 101, 2),
            Order("S2", "SELL", 102, 5),
            Order("B1", "BUY", 102, 6),
            Order("M1", "BUY", None, 2, order_type=OrderType.MARKET),
            Order("C1", "SELL", 105, 3),
        ]
        trades = [trade for order in orders for trade in engine.submit(order)]
        return (
            [
                (
                    trade.symbol,
                    trade.buy_order_id,
                    trade.sell_order_id,
                    trade.price,
                    trade.quantity,
                )
                for trade in trades
            ],
            engine.book.snapshot(),
            [engine.status(order.id) for order in orders],
        )

    def cython_kernel(price, quantity, is_buy, prices, quantities):
        return _matcher._cython_match_orders(
            price,
            quantity,
            is_buy,
            array("d", prices),
            array("q", quantities),
        )

    reference = replay(python_match_orders)
    optimized = replay(cython_kernel)
    assert optimized == reference


def test_duplicate_id_rejected_before_matching():
    e = MatchingEngine()
    resting = Order("DUP", "SELL", 100, 5)
    incoming = Order("DUP", "BUY", 100, 5)
    e.submit(resting)

    try:
        e.submit(incoming)
        assert False, "Expected duplicate order ID to be rejected"
    except ValueError as exc:
        assert str(exc) == "Duplicate order id DUP"

    assert e.trades == []
    assert e.book.get("DUP") is resting
    assert resting.remaining == 5
    assert incoming.remaining == 5


def test_order_id_cannot_be_reused_after_fill_or_cancel():
    e = MatchingEngine()
    e.submit(Order("FILLED", "SELL", 100, 1))
    e.submit(Order("BUY", "BUY", 100, 1))
    e.submit(Order("CANCELLED", "BUY", 99, 1))
    assert e.cancel("CANCELLED")

    for duplicate in (
        Order("FILLED", "BUY", 99, 1),
        Order("CANCELLED", "SELL", 101, 1),
    ):
        try:
            e.submit(duplicate)
            assert False, "Expected historical order ID reuse to be rejected"
        except ValueError as exc:
            assert str(exc) == f"Duplicate order id {duplicate.id}"
        assert duplicate.remaining == duplicate.quantity

    assert len(e.book) == 0
    assert len(e.trades) == 1


def test_conservation_of_quantity():
    import random
    random.seed(7)
    e = MatchingEngine()
    total = 0
    for i in range(500):
        q = random.randint(1, 20); total += q
        e.submit(Order(f"O{i}", random.choice(("BUY", "SELL")),
                       random.choice((99, 100, 101)), q))
    traded = sum(t.quantity for t in e.trades)
    resting = sum(o.remaining for o in e.book._live.values())
    assert total == 2 * traded + resting

from chronosmatch import Order, OrderBook


def test_best_bid_ask_ordering():
    b = OrderBook()
    b.add(Order("B1", "BUY", 99, 5)); b.add(Order("B2", "BUY", 100, 5))
    b.add(Order("S1", "SELL", 102, 5)); b.add(Order("S2", "SELL", 101, 5))
    assert b.best_bid().id == "B2" and b.best_ask().id == "S2"
    assert b.spread() == 1


def test_time_priority_same_price():
    b = OrderBook()
    b.add(Order("B1", "BUY", 100, 5)); b.add(Order("B2", "BUY", 100, 5))
    assert b.best_bid().id == "B1"


def test_cancel_and_lookup():
    b = OrderBook()
    b.add(Order("B1", "BUY", 100, 5))
    assert b.get("B1") is not None
    assert b.cancel("B1") and b.cancel("B1") is False
    assert b.best_bid() is None and len(b) == 0


def test_duplicate_id_rejected():
    b = OrderBook()
    b.add(Order("X", "BUY", 100, 5))
    try:
        b.add(Order("X", "SELL", 101, 5))
        assert False
    except ValueError:
        pass


def test_snapshot_aggregates_levels():
    b = OrderBook()
    b.add(Order("B1", "BUY", 100, 5)); b.add(Order("B2", "BUY", 100, 3))
    b.add(Order("B3", "BUY", 99, 2))
    assert b.snapshot()["bids"] == [(100, 8), (99, 2)]

from chronosmatch import Order, MatchingEngine


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
    assert e.book.best_bid().remaining == 4 and e.status("B") == "OPEN"


def test_partial_fill_resting_larger():
    e = MatchingEngine()
    e.submit(Order("S", "SELL", 100, 10))
    e.submit(Order("B", "BUY", 100, 4))
    assert e.book.best_ask().remaining == 6 and e.status("S") == "OPEN"
    assert e.status("B") == "DONE"


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

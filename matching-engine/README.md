# Branch 2 - matching-engine (ChronosMatch)

My responsibilities: match orders, price-time priority, partial fills and
completed orders, maintain the order book.

Files I own: `chronosmatch/matching_engine.py`, `chronosmatch/order_book.py`
(+ `tests/test_order_book.py`, `tests/test_matching.py`).

`chronosmatch/orders.py` belongs to Branch 1 (order-management). It is included
only so this branch runs on its own; on merge keep the teammate's version
(the engine needs: `Order.id/.side/.price/.remaining`, and `Side.BUY/SELL`).

## How it works
- Bids: max-heap by price; asks: min-heap by price; ties broken by arrival
  sequence number -> price-time priority.
- An incoming order trades against the best opposite price while prices cross,
  at the resting order's price. Leftover quantity rests on the book.
- Partial fill: `remaining` is reduced on both orders; an order with
  `remaining == 0` is completed and removed.
- Cancels are lazy: the order is marked and dropped from the heap when it
  reaches the top (O(log n)).

## Run
```
python -m chronosmatch
python -m pytest -v
```

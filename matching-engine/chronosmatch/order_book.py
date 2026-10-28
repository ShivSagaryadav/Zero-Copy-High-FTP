"""Order book holding pending buy and sell orders with price-time priority."""
from __future__ import annotations

import heapq
import itertools
from typing import Optional

from .orders import Order, Side


class OrderBook:
    """Best bid = highest buy price; best ask = lowest sell price.
    Ties are broken by arrival order (price-time priority)."""

    def __init__(self) -> None:
        self._bids: list = []   # (-price, seq, order)
        self._asks: list = []   # (price, seq, order)
        self._seq = itertools.count()
        self._live: dict[str, Order] = {}

    def add(self, order: Order) -> None:
        if order.id in self._live:
            raise ValueError(f"Duplicate order id {order.id}")
        self._live[order.id] = order
        n = next(self._seq)
        if order.side is Side.BUY:
            heapq.heappush(self._bids, (-order.price, n, order))
        else:
            heapq.heappush(self._asks, (order.price, n, order))

    def cancel(self, order_id: str) -> bool:
        order = self._live.pop(order_id, None)
        if order is None:
            return False
        order.remaining = 0          # lazily removed from heaps
        return True

    @staticmethod
    def _clean(heap: list) -> None:
        while heap and heap[0][2].remaining == 0:
            heapq.heappop(heap)

    def best_bid(self) -> Optional[Order]:
        self._clean(self._bids)
        return self._bids[0][2] if self._bids else None

    def best_ask(self) -> Optional[Order]:
        self._clean(self._asks)
        return self._asks[0][2] if self._asks else None

    def remove_if_filled(self, order: Order) -> None:
        if order.remaining == 0:
            self._live.pop(order.id, None)

    def get(self, order_id: str) -> Optional[Order]:
        """Look up a live (unfilled, uncancelled) order by id."""
        return self._live.get(order_id)

    def spread(self) -> Optional[float]:
        bid, ask = self.best_bid(), self.best_ask()
        return None if bid is None or ask is None else round(ask.price - bid.price, 10)

    def __len__(self) -> int:
        return len(self._live)

    def snapshot(self, depth: int = 5) -> dict:
        def agg(heap, reverse):
            levels: dict[float, int] = {}
            for _, _, o in heap:
                if o.remaining:
                    levels[o.price] = levels.get(o.price, 0) + o.remaining
            return sorted(levels.items(), reverse=reverse)[:depth]
        return {"bids": agg(self._bids, True), "asks": agg(self._asks, False)}

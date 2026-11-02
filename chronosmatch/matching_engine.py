"""Component B - Matching engine: full and partial fills."""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from typing import List

from . import _matcher
from .order_book import OrderBook
from .orders import Order, Side


@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: int
    buy_order_id: str
    sell_order_id: str
    price: float
    quantity: int
    timestamp: float
    latency_ns: int = 0
    end_to_end_latency_ns: int = 0
    aggressor_order_quantity: int = 0

    @property
    def value(self) -> float:
        return round(self.price * self.quantity, 2)


class MatchingEngine:
    def __init__(self) -> None:
        self.book = OrderBook()
        self.trades: List[Trade] = []
        self._ids = itertools.count(1)
        self._seen_order_ids: set[str] = set()
        self.matcher_backend = _matcher.BACKEND

    def submit(self, order: Order) -> List[Trade]:
        """Match the incoming order against the book; any rest goes on the book.
        Trades execute at the resting order's price."""
        book = self.book
        if order.id in self._seen_order_ids:
            raise ValueError(f"Duplicate order id {order.id}")
        self._seen_order_ids.add(order.id)
        engine_started_ns = time.perf_counter_ns()
        matched_orders: list[tuple[Order, int]] = []
        while order.remaining > 0:
            if order.side is Side.BUY:
                resting = book.best_ask()
                if resting is None or resting.price > order.price:
                    break
            else:
                resting = book.best_bid()
                if resting is None or resting.price < order.price:
                    break
            fills, remaining = _matcher.match_orders(
                order.price,
                order.remaining,
                order.side is Side.BUY,
                [resting.price],
                [resting.remaining],
            )
            quantity = fills[0]
            if quantity == 0:
                break
            order.remaining = remaining
            resting.remaining -= quantity
            matched_orders.append((resting, quantity))
            book.remove_if_filled(resting)
        if order.remaining > 0:
            book.add(order)
        matched_ns = time.perf_counter_ns()
        engine_latency_ns = matched_ns - engine_started_ns
        end_to_end_latency_ns = max(0, matched_ns - order.created_ns)
        new_trades: List[Trade] = []
        for resting, quantity in matched_orders:
            buy, sell = (order, resting) if order.side is Side.BUY else (resting, order)
            new_trades.append(
                Trade(
                    next(self._ids),
                    buy.id,
                    sell.id,
                    resting.price,
                    quantity,
                    time.time(),
                    engine_latency_ns,
                    end_to_end_latency_ns,
                    order.quantity,
                )
            )
        self.trades.extend(new_trades)
        return new_trades

    def cancel(self, order_id: str) -> bool:
        return self.book.cancel(order_id)

    def status(self, order_id: str) -> str:
        """'OPEN' if resting on the book, else 'DONE' (filled/cancelled/unknown)."""
        return "OPEN" if self.book.get(order_id) else "DONE"

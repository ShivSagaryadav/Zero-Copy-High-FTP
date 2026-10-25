"""Component B - Matching engine: full and partial fills."""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from typing import List

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

    @property
    def value(self) -> float:
        return round(self.price * self.quantity, 2)


class MatchingEngine:
    def __init__(self) -> None:
        self.book = OrderBook()
        self.trades: List[Trade] = []
        self._ids = itertools.count(1)

    def submit(self, order: Order) -> List[Trade]:
        """Match the incoming order against the book; any rest goes on the book.
        Trades execute at the resting order's price."""
        new_trades: List[Trade] = []
        book = self.book
        while order.remaining > 0:
            if order.side is Side.BUY:
                resting = book.best_ask()
                if resting is None or resting.price > order.price:
                    break
            else:
                resting = book.best_bid()
                if resting is None or resting.price < order.price:
                    break
            qty = min(order.remaining, resting.remaining)
            order.remaining -= qty
            resting.remaining -= qty
            buy, sell = (order, resting) if order.side is Side.BUY else (resting, order)
            new_trades.append(Trade(next(self._ids), buy.id, sell.id,
                                    resting.price, qty, time.time()))
            book.remove_if_filled(resting)
        if order.remaining > 0:
            book.add(order)
        self.trades.extend(new_trades)
        return new_trades

    def cancel(self, order_id: str) -> bool:
        return self.book.cancel(order_id)

    def status(self, order_id: str) -> str:
        """'OPEN' if resting on the book, else 'DONE' (filled/cancelled/unknown)."""
        return "OPEN" if self.book.get(order_id) else "DONE"

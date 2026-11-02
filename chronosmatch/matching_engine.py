"""Component B - Matching engine: full and partial fills."""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from typing import List

from . import _matcher
from .order_book import OrderBook
from .orders import Order, OrderStatus, OrderType, Side, normalize_symbol


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
    symbol: str = "DEFAULT"

    @property
    def value(self) -> float:
        return round(self.price * self.quantity, 2)


class MatchingEngine:
    def __init__(self) -> None:
        self._books: dict[str, OrderBook] = {}
        self.trades: List[Trade] = []
        self._ids = itertools.count(1)
        self._seen_order_ids: set[str] = set()
        self._orders: dict[str, Order] = {}
        self.matcher_backend = _matcher.BACKEND

    @property
    def book(self) -> OrderBook:
        """Backward-compatible access to the default-symbol order book."""
        return self.book_for("DEFAULT")

    def book_for(self, symbol: str) -> OrderBook:
        normalized = normalize_symbol(symbol)
        if normalized not in self._books:
            self._books[normalized] = OrderBook()
        return self._books[normalized]

    def submit(self, order: Order) -> List[Trade]:
        """Match the incoming order against the book; any rest goes on the book.
        Trades execute at the resting order's price."""
        book = self.book
        if order.id in self._seen_order_ids:
            raise ValueError(f"Duplicate order id {order.id}")
        self._seen_order_ids.add(order.id)
        self._orders[order.id] = order
        book = self.book_for(order.symbol)
        engine_started_ns = time.perf_counter_ns()
        matched_orders: list[tuple[Order, int]] = []
        while order.remaining > 0:
            if order.side is Side.BUY:
                resting = book.best_ask()
                if resting is None or (
                    order.order_type is OrderType.LIMIT
                    and resting.price > order.price
                ):
                    break
            else:
                resting = book.best_bid()
                if resting is None or (
                    order.order_type is OrderType.LIMIT
                    and resting.price < order.price
                ):
                    break
            fills, remaining = _matcher.match_orders(
                (
                    order.price
                    if order.order_type is OrderType.LIMIT
                    else (float("inf") if order.side is Side.BUY else -float("inf"))
                ),
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
            resting.status = (
                OrderStatus.FILLED
                if resting.remaining == 0
                else OrderStatus.PARTIALLY_FILLED
            )
            matched_orders.append((resting, quantity))
            book.remove_if_filled(resting)
        if order.remaining == 0:
            order.status = OrderStatus.FILLED
        elif order.order_type is OrderType.MARKET:
            order.status = (
                OrderStatus.PARTIALLY_FILLED
                if matched_orders
                else OrderStatus.CANCELLED
            )
        else:
            order.status = (
                OrderStatus.PARTIALLY_FILLED
                if matched_orders
                else OrderStatus.OPEN
            )
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
                    order.symbol,
                )
            )
        self.trades.extend(new_trades)
        return new_trades

    def cancel(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None or order.status not in (
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
        ):
            return False
        if not self.book_for(order.symbol).cancel(order_id):
            return False
        order.status = OrderStatus.CANCELLED
        return True

    def status(self, order_id: str) -> str:
        """Return the order lifecycle status, or UNKNOWN for an unseen ID."""
        order = self._orders.get(order_id)
        return order.status.value if order is not None else "UNKNOWN"

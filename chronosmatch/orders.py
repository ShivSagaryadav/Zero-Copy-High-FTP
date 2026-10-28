"""Component A - Order management: the Order class and its validation."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderValidationError(ValueError):
    """Raised when an order has invalid details."""


@dataclass(slots=True)
class Order:
    id: str
    side: Side
    price: float
    quantity: int
    timestamp: float = field(default_factory=time.time)
    remaining: int = field(init=False)
    created_ns: int = field(default_factory=time.perf_counter_ns, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise OrderValidationError("Order ID must be a non-empty string")
        raw = self.side.value if isinstance(self.side, Side) else str(self.side)
        try:
            self.side = Side(raw.upper())
        except ValueError:
            raise OrderValidationError("Side must be BUY or SELL") from None
        try:
            price_is_finite = math.isfinite(self.price)
        except (OverflowError, TypeError):
            price_is_finite = False
        if (
            isinstance(self.price, bool)
            or not isinstance(self.price, (int, float))
            or not price_is_finite
            or self.price <= 0
        ):
            raise OrderValidationError("Price must be positive and finite")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int) \
                or self.quantity <= 0:
            raise OrderValidationError("Quantity must be a positive integer")
        self.remaining = self.quantity

    @property
    def is_filled(self) -> bool:
        return self.remaining == 0

    def __str__(self) -> str:
        return (f"Order(id={self.id}, side={self.side.value}, "
                f"price={self.price}, quantity={self.quantity})")


if __name__ == "__main__":
    print(Order("ORD001", "BUY", 100.5, 10))
    for label, args in [("Bad side", ("ORD2", "HOLD", 100.5, 10)),
                        ("Bad price", ("ORD3", "BUY", -5, 10)),
                        ("Bad quantity", ("ORD4", "SELL", 100.5, 0))]:
        try:
            Order(*args)
        except OrderValidationError as e:
            print(f"{label} - Passed: {e}")

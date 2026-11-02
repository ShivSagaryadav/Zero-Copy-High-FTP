"""Pure-Python matching kernel used when the optional Cython module is absent."""
from __future__ import annotations

from typing import Sequence


def match_orders(
    incoming_price: float,
    incoming_quantity: int,
    incoming_is_buy: bool,
    resting_prices: Sequence[float],
    resting_quantities: Sequence[int],
) -> tuple[list[int], int]:
    fills = [0] * len(resting_prices)
    remaining = incoming_quantity
    for index, (price, quantity) in enumerate(
        zip(resting_prices, resting_quantities)
    ):
        if remaining <= 0:
            break
        if incoming_is_buy and price > incoming_price:
            break
        if not incoming_is_buy and price < incoming_price:
            break
        fill = min(remaining, quantity)
        fills[index] = fill
        remaining -= fill
    return fills, remaining

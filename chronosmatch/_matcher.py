"""Select the compiled matcher when built, otherwise use the Python kernel."""
from __future__ import annotations

from array import array

from ._python_matcher import match_orders as _python_match_orders

try:
    from ._cython_matcher import match_orders as _cython_match_orders
except ImportError:
    _cython_match_orders = None


BACKEND = "cython" if _cython_match_orders is not None else "python"
_MAX_NATIVE_QUANTITY = 2**63 - 1


def match_orders(
    incoming_price: float,
    incoming_quantity: int,
    incoming_is_buy: bool,
    resting_prices: list[float],
    resting_quantities: list[int],
) -> tuple[list[int], int]:
    if (
        _cython_match_orders is not None
        and incoming_quantity <= _MAX_NATIVE_QUANTITY
        and all(0 <= quantity <= _MAX_NATIVE_QUANTITY for quantity in resting_quantities)
    ):
        return _cython_match_orders(
            incoming_price,
            incoming_quantity,
            incoming_is_buy,
            array("d", resting_prices),
            array("q", resting_quantities),
        )
    return _python_match_orders(
        incoming_price,
        incoming_quantity,
        incoming_is_buy,
        resting_prices,
        resting_quantities,
    )

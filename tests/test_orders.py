import pytest

from chronosmatch import Order, OrderValidationError


@pytest.mark.parametrize("price", [float("nan"), float("inf"), float("-inf")])
def test_order_rejects_non_finite_prices(price):
    with pytest.raises(OrderValidationError, match="finite"):
        Order("X", "BUY", price, 1)

from array import array

import pytest

from chronosmatch import _cython_matcher


@pytest.mark.parametrize(
    (
        "incoming_price",
        "incoming_quantity",
        "incoming_is_buy",
        "prices",
        "quantities",
        "expected",
    ),
    [
        (100.0, 5, True, [99.0, 101.0, 98.0], [2, 7, 3], ([2, 0, 0], 3)),
        (100.0, 5, False, [101.0, 99.0, 102.0], [2, 7, 3], ([2, 0, 0], 3)),
        (100.0, 2, True, [99.0, 100.0, 100.0], [1, 1, 1], ([1, 1, 0], 0)),
        (100.0, 0, True, [99.0, 100.0], [1, 1], ([0, 0], 0)),
    ],
)
def test_native_matcher_initializes_every_fill_slot(
    incoming_price,
    incoming_quantity,
    incoming_is_buy,
    prices,
    quantities,
    expected,
):
    result = _cython_matcher.match_orders(
        incoming_price,
        incoming_quantity,
        incoming_is_buy,
        array("d", prices),
        array("q", quantities),
    )
    assert result == expected


def test_native_matcher_handles_empty_book():
    assert _cython_matcher.match_orders(
        100.0, 5, True, array("d"), array("q")
    ) == ([], 5)
from array import array

def match_orders(
    incoming_price: float,
    incoming_quantity: int,
    incoming_is_buy: bool,
    resting_prices: array,
    resting_quantities: array,
) -> tuple[list[int], int]: ...
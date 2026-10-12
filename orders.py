
from datetime import datetime


class Order:
    def __init__(self, order_id, side, price, quantity):
        if side not in ("BUY", "SELL"):
            raise ValueError("Side must be BUY or SELL")

        if price <= 0:
            raise ValueError("Price must be positive")

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        self.order_id = order_id
        self.side = side
        self.price = price
        self.quantity = quantity
        self.timestamp = datetime.now()

    def __repr__(self):
        return (
            f"Order(id={self.order_id}, side={self.side}, "
            f"price={self.price}, quantity={self.quantity})"
        )


if __name__ == "__main__":
    order = Order("ORD001", "BUY", 100.50, 10)
    print(order)

# Test 1: Valid order
order1 = Order("ORD002", "BUY", 100.5, 10)
print("Test 1 - Valid order:", order1)

# Test 2: Invalid side
try:
    Order("ORD003", "HOLD", 100.5, 10)
except ValueError as e:
    print("Test 2 - Passed:", e)

# Test 3: Invalid price
try:
    Order("ORD004", "BUY", -10, 10)
except ValueError as e:
    print("Test 3 - Passed:", e)

# Test 4: Invalid quantity
try:
    Order("ORD005", "SELL", 100, 0)
except ValueError as e:
    print("Test 4 - Passed:", e)

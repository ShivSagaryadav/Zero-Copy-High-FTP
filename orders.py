
from datetime import datetime


class Order:
    def __init__(self, order_id, side, price, quantity):
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("Order ID must not be empty")

        if side not in ("BUY", "SELL"):
            raise ValueError("Side must be BUY or SELL")

        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or price <= 0
        ):
            raise ValueError("Price must be a positive number")

        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity <= 0
        ):
            raise ValueError("Quantity must be a positive integer")

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

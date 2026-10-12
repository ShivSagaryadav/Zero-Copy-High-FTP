
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

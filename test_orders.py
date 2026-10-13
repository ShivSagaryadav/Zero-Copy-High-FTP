
import unittest
from orders import Order


class TestOrder(unittest.TestCase):

    def test_valid_buy_order(self):
        order = Order("ORD001", "BUY", 100.5, 10)
        self.assertEqual(order.side, "BUY")
        self.assertEqual(order.price, 100.5)
        self.assertEqual(order.quantity, 10)

    def test_valid_sell_order(self):
        order = Order("ORD002", "SELL", 101.0, 5)
        self.assertEqual(order.side, "SELL")

    def test_empty_order_id(self):
        with self.assertRaises(ValueError):
            Order("", "BUY", 100.5, 10)

    def test_invalid_side(self):
        with self.assertRaises(ValueError):
            Order("ORD003", "HOLD", 100.5, 10)

    def test_zero_price(self):
        with self.assertRaises(ValueError):
            Order("ORD004", "BUY", 0, 10)

    def test_negative_price(self):
        with self.assertRaises(ValueError):
            Order("ORD005", "BUY", -10, 10)

    def test_zero_quantity(self):
        with self.assertRaises(ValueError):
            Order("ORD006", "BUY", 100.5, 0)

    def test_decimal_quantity(self):
        with self.assertRaises(ValueError):
            Order("ORD007", "BUY", 100.5, 2.5)


if __name__ == "__main__":
    unittest.main()

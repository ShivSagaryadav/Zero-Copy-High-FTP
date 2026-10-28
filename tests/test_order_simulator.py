
import unittest

from order_simulator import generate_orders, run_simulation


class TestOrderSimulator(unittest.IsolatedAsyncioTestCase):

    async def test_generates_requested_orders(self):
        orders = [
            order async for order in generate_orders(100)
        ]

        self.assertEqual(len(orders), 100)

    async def test_order_values_are_valid(self):
        orders = [
            order async for order in generate_orders(100)
        ]

        for order in orders:
            self.assertIn(order.side, ["BUY", "SELL"])
            self.assertGreater(order.price, 0)
            self.assertGreater(order.quantity, 0)

    async def test_fixed_seed_is_repeatable(self):
        first = [
            order async for order in generate_orders(20, seed=42)
        ]
        second = [
            order async for order in generate_orders(20, seed=42)
        ]

        first_values = [
            (o.order_id, o.side, o.price, o.quantity)
            for o in first
        ]
        second_values = [
            (o.order_id, o.side, o.price, o.quantity)
            for o in second
        ]

        self.assertEqual(first_values, second_values)

    async def test_simulation_consumes_all_orders(self):
        result = await run_simulation(count=500, seed=42)

        self.assertEqual(result["requested"], 500)
        self.assertEqual(result["consumed"], 500)
        self.assertGreater(result["elapsed_seconds"], 0)
        self.assertGreater(
            result["throughput_orders_per_second"], 0
        )

    async def test_simulation_rejects_invalid_counts(self):
        for count in (-1, 1.5, True):
            with self.subTest(count=count):
                with self.assertRaisesRegex(
                    ValueError, "count must be a non-negative integer"
                ):
                    await run_simulation(count=count)

    async def test_order_generator_rejects_invalid_counts(self):
        for count in (-1, 1.5, True):
            with self.subTest(count=count):
                with self.assertRaisesRegex(
                    ValueError, "count must be a non-negative integer"
                ):
                    _ = [order async for order in generate_orders(count)]


if __name__ == "__main__":
    unittest.main()

import math
import unittest

from ring_buffer import RingBuffer


class TestRingBuffer(unittest.TestCase):

    def setUp(self):
        self.buffer = RingBuffer(capacity=2)

    def tearDown(self):
        self.buffer.close()

    def test_write_and_read_order(self):
        self.buffer.write_order(1, 100.5, 10)
        result = self.buffer.read_order()
        self.assertEqual(result, (1, 100.5, 10))

    def test_buffer_full(self):
        self.buffer.write_order(1, 100.0, 5)
        self.buffer.write_order(2, 101.0, 6)

        with self.assertRaises(BufferError):
            self.buffer.write_order(3, 102.0, 7)

    def test_buffer_empty(self):
        with self.assertRaises(BufferError):
            self.buffer.read_order()

    def test_fifo_order(self):
        self.buffer.write_order(1, 100.0, 5)
        self.buffer.write_order(2, 101.0, 6)

        self.assertEqual(self.buffer.read_order(), (1, 100.0, 5))
        self.assertEqual(self.buffer.read_order(), (2, 101.0, 6))

    def test_wraparound(self):
        self.buffer.write_order(1, 100.0, 5)
        self.buffer.write_order(2, 101.0, 6)
        self.buffer.read_order()

        self.buffer.write_order(3, 102.0, 7)

        self.assertEqual(self.buffer.read_order(), (2, 101.0, 6))
        self.assertEqual(self.buffer.read_order(), (3, 102.0, 7))


    def test_invalid_order_id(self):
        with self.assertRaises(ValueError):
            self.buffer.write_order(-1, 100.0, 5)

    def test_quantity_exceeds_uint32_limit(self):
        with self.assertRaisesRegex(
            ValueError, "Quantity must be a positive 32-bit integer"
        ):
            self.buffer.write_order(1, 100.0, 2**32)

    def test_invalid_price(self):
        with self.assertRaises(ValueError):
            self.buffer.write_order(1, 0, 5)

    def test_invalid_quantity(self):
        with self.assertRaises(ValueError):
            self.buffer.write_order(1, 100.0, 0)

    def test_nan_price(self):
        with self.assertRaises(ValueError):
            self.buffer.write_order(1, math.nan, 5)

    def test_infinite_price(self):
        with self.assertRaises(ValueError):
            self.buffer.write_order(1, math.inf, 5)
            
    def test_read_after_close(self):
        self.buffer.close()
        with self.assertRaisesRegex(ValueError, "Ring buffer is closed"):
            self.buffer.read_order()

    def test_write_after_close(self):
        self.buffer.close()
        with self.assertRaisesRegex(ValueError, "Ring buffer is closed"):
            self.buffer.write_order(1, 100.0, 5)

    def test_close_twice(self):
        self.buffer.close()
        self.buffer.close()
if __name__ == "__main__":
    unittest.main()

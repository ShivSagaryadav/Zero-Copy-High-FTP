import multiprocessing
import unittest

from shared_order_buffer import RECORD_SIZE, SharedOrderBuffer


def _child_write(name, lock, result_queue):
    buffer = SharedOrderBuffer.attach(name, lock)
    try:
        buffer.write_order(42, 101.25, 7, "SELL")
        result_queue.put("written")
    finally:
        buffer.close()


class TestSharedOrderBuffer(unittest.TestCase):
    def setUp(self):
        self.lock = multiprocessing.Lock()
        self.buffer = SharedOrderBuffer.create(4, self.lock)

    def tearDown(self):
        name = self.buffer.name
        self.buffer.close()
        self.buffer.unlink()

    def test_compact_record_size(self):
        self.assertEqual(RECORD_SIZE, 24)

    def test_fifo_round_trip_preserves_side(self):
        self.buffer.write_order(1, 100.5, 3, "BUY")
        self.buffer.write_order(2, 101.0, 4, "SELL")
        self.assertEqual(
            self.buffer.read_order(),
            {"order_id": 1, "price": 100.5, "quantity": 3, "side": "BUY"},
        )
        self.assertEqual(
            self.buffer.read_order(),
            {"order_id": 2, "price": 101.0, "quantity": 4, "side": "SELL"},
        )
        self.assertIsNone(self.buffer.read_order())

    def test_full_and_wraparound(self):
        self.buffer.write_order(1, 10, 1, "BUY")
        self.buffer.write_order(2, 20, 1, "SELL")
        self.buffer.write_order(3, 30, 1, "BUY")
        with self.assertRaises(BufferError):
            self.buffer.write_order(4, 40, 1, "SELL")
        self.assertEqual(self.buffer.read_order()["order_id"], 1)
        self.buffer.write_order(4, 40, 1, "SELL")
        self.assertEqual(
            [self.buffer.read_order()["order_id"] for _ in range(3)],
            [2, 3, 4],
        )

    def test_rejects_invalid_fields(self):
        invalid = [
            (True, 10, 1, "BUY"),
            (1, float("nan"), 1, "BUY"),
            (1, 10, 0, "BUY"),
            (1, 10, 1, "BID"),
        ]
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.buffer.write_order(*args)

    def test_cross_process_shared_memory(self):
        ctx = multiprocessing.get_context("spawn")
        lock = ctx.Lock()
        buffer = SharedOrderBuffer.create(4, lock)
        queue = ctx.Queue()
        process = ctx.Process(target=_child_write, args=(buffer.name, lock, queue))
        try:
            process.start()
            process.join(timeout=10)
            self.assertEqual(process.exitcode, 0)
            self.assertEqual(queue.get(timeout=2), "written")
            self.assertEqual(
                buffer.read_order(),
                {"order_id": 42, "price": 101.25, "quantity": 7, "side": "SELL"},
            )
        finally:
            if process.is_alive():
                process.terminate()
                process.join()
            buffer.close()
            buffer.unlink()
            queue.close()


if __name__ == "__main__":
    unittest.main()

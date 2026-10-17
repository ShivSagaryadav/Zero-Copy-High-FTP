
import asyncio
import time

from ring_buffer import RingBuffer


async def generate_orders(buffer, total_orders):
    """Generate mock orders asynchronously and write them to the buffer."""
    generated = 0
    start_time = time.perf_counter()

    while generated < total_orders:
        # Wait until the buffer has space.
        while buffer.count == buffer.capacity:
            await asyncio.sleep(0)

        order_id = generated + 1
        side = "BUY" if order_id % 2 == 1 else "SELL"
        price = 100.0 + (order_id % 100) * 0.01
        quantity = (order_id % 10) + 1

        # The current ring buffer stores numeric IDs, price, and quantity.
        buffer.write_order(order_id, price, quantity)

        generated += 1

        # Let other asynchronous tasks run periodically.
        if generated % 1000 == 0:
            await asyncio.sleep(0)

    elapsed = time.perf_counter() - start_time
    rate = generated / elapsed if elapsed > 0 else 0

    print(f"Orders generated: {generated}")
    print(f"Elapsed time: {elapsed:.4f} seconds")
    print(f"Generation rate: {rate:.0f} orders/second")
    print("Note: BUY/SELL side is generated but is not stored in the current buffer.")


async def consume_orders(buffer, total_orders):
    """Read and consume orders so the buffer does not fill up."""
    consumed = 0

    while consumed < total_orders:
        if buffer.count > 0:
            buffer.read_order()
            consumed += 1
        else:
            await asyncio.sleep(0)


async def main():
    total_orders = 10_000
    buffer = RingBuffer(capacity=1024)

    try:
        await asyncio.gather(
            generate_orders(buffer, total_orders),
            consume_orders(buffer, total_orders),
        )
    finally:
        buffer.close()


if __name__ == "__main__":
    asyncio.run(main())

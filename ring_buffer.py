
import mmap
import struct
import math

class RingBuffer:
    """Fixed-capacity ring buffer backed by memory-mapped storage."""

    RECORD_FORMAT = "<QdI"
    RECORD_SIZE = struct.calcsize(RECORD_FORMAT)

    def __init__(self, capacity=1024):
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
            raise ValueError("Capacity must be a positive integer")

        self.capacity = capacity
        self.write_index = 0
        self.read_index = 0
        self.count = 0

        self.memory = mmap.mmap(
            -1,
            capacity * self.RECORD_SIZE,
        )

    def write_order(self, order_id, price, quantity):
        if self.count == self.capacity:
            raise BufferError("Ring buffer is full")

        if not isinstance(order_id, int) or isinstance(order_id, bool) or not 0 <= order_id < 2**64:
            raise ValueError("Order ID must be an unsigned 64-bit integer")

        if (
    not isinstance(price, (int, float))
    or isinstance(price, bool)
    or not math.isfinite(price)
    or price <= 0
        ):
         raise ValueError("Price must be a finite positive number")

        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("Quantity must be a positive integer")

        record = struct.pack(
            self.RECORD_FORMAT,
            order_id,
            float(price),
            quantity,
        )

        offset = self.write_index * self.RECORD_SIZE
        self.memory[offset:offset + self.RECORD_SIZE] = record

        self.write_index = (self.write_index + 1) % self.capacity
        self.count += 1

    def read_order(self):
        if self.count == 0:
            raise BufferError("Ring buffer is empty")

        offset = self.read_index * self.RECORD_SIZE
        record = self.memory[offset:offset + self.RECORD_SIZE]
        order = struct.unpack(self.RECORD_FORMAT, record)

        self.read_index = (self.read_index + 1) % self.capacity
        self.count -= 1

        return order

    def close(self):
        self.memory.close()

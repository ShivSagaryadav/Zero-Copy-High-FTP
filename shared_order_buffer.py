"""Fixed-record shared-memory order buffer prototype.

This module is a separate prototype for the zero-copy-optimization branch.
It does not replace the team's existing ring_buffer.py interface yet.

Record layout (little-endian, 24 bytes):
    order_id : unsigned 64-bit integer (8 bytes)
    price    : IEEE-754 double (8 bytes)
    quantity : unsigned 32-bit integer (4 bytes)
    side     : unsigned byte: 0 = BUY, 1 = SELL (1 byte)
    padding  : 3 bytes (reserved; keeps record size at 24 bytes)

The shared memory contains a fixed header followed by fixed-size records.
A multiprocessing lock must be shared by all processes using the same buffer.
The lock protects metadata and record writes/reads; this is a correctness-first
prototype, not a lock-free or fully lock-free zero-copy queue.
"""

from __future__ import annotations

import math
import struct
from multiprocessing import Lock, shared_memory
from typing import Optional

MAGIC = b"ZCO1"
VERSION = 1
HEADER_FORMAT = "<4sIIII"  # magic, version, capacity, read_index, write_index
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
RECORD_FORMAT = "<QdIB3x"
RECORD_SIZE = struct.calcsize(RECORD_FORMAT)
BUY = 0
SELL = 1


class SharedOrderBuffer:
    """A bounded FIFO buffer backed by multiprocessing shared memory.

    Create with ``SharedOrderBuffer.create(capacity)`` in the parent process.
    Pass ``name`` and the same multiprocessing lock to child processes, then
    attach with ``SharedOrderBuffer.attach(name, lock)``.
    """

    def __init__(self, shm: shared_memory.SharedMemory, lock: Lock, owner: bool):
        self._shm = shm
        self._lock = lock
        self._owner = owner
        self._closed = False
        self._validate_header()

    @classmethod
    def create(cls, capacity: int, lock: Optional[Lock] = None) -> "SharedOrderBuffer":
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        shm = shared_memory.SharedMemory(
            create=True, size=HEADER_SIZE + capacity * RECORD_SIZE
        )
        lock = lock if lock is not None else Lock()
        struct.pack_into(HEADER_FORMAT, shm.buf, 0, MAGIC, VERSION, capacity, 0, 0)
        return cls(shm, lock, owner=True)

    @classmethod
    def attach(cls, name: str, lock: Lock) -> "SharedOrderBuffer":
        """Attach to an existing shared buffer using its name and shared lock."""
        shm = shared_memory.SharedMemory(name=name, create=False)
        return cls(shm, lock, owner=False)

    @property
    def name(self) -> str:
        return self._shm.name

    @property
    def capacity(self) -> int:
        return self._header()[2]

    @property
    def record_size(self) -> int:
        return RECORD_SIZE

    @property
    def max_records(self) -> int:
        return self.capacity

    def _header(self):
        if self._closed:
            raise RuntimeError("buffer is closed")
        return struct.unpack_from(HEADER_FORMAT, self._shm.buf, 0)

    def _validate_header(self) -> None:
        magic, version, capacity, read_index, write_index = struct.unpack_from(
            HEADER_FORMAT, self._shm.buf, 0
        )
        if magic != MAGIC or version != VERSION or capacity <= 0:
            raise ValueError("shared memory does not contain a supported order buffer")
        if read_index >= capacity or write_index >= capacity:
            raise ValueError("shared buffer header indices are invalid")
        if len(self._shm.buf) < HEADER_SIZE + capacity * RECORD_SIZE:
            raise ValueError("shared memory region is smaller than its declared capacity")

    def _set_indices(self, read_index: int, write_index: int) -> None:
        magic, version, capacity, _, _ = self._header()
        struct.pack_into(
            HEADER_FORMAT, self._shm.buf, 0,
            magic, version, capacity, read_index, write_index
        )

    def _next(self, index: int) -> int:
        return (index + 1) % self.capacity

    def _is_empty(self, read_index: int, write_index: int) -> bool:
        return read_index == write_index

    def _count(self, read_index: int, write_index: int) -> int:
        return (write_index - read_index) % self.capacity

    def write_order(self, order_id: int, price: float, quantity: int, side: str) -> None:
        """Write one order record; raises BufferError if full.

        One slot is reserved to distinguish full from empty, so usable capacity
        is ``capacity - 1``.
        """
        if not isinstance(order_id, int) or isinstance(order_id, bool) or not 0 <= order_id < 2**64:
            raise ValueError("order_id must be an unsigned 64-bit integer")
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise ValueError("price must be a finite positive number")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or not 0 < quantity < 2**32:
            raise ValueError("quantity must be a positive unsigned 32-bit integer")
        if side not in ("BUY", "SELL"):
            raise ValueError("side must be 'BUY' or 'SELL'")
        side_code = BUY if side == "BUY" else SELL

        with self._lock:
            _, _, capacity, read_index, write_index = self._header()
            next_index = (write_index + 1) % capacity
            if next_index == read_index:
                raise BufferError("shared order buffer is full")
            offset = HEADER_SIZE + write_index * RECORD_SIZE
            struct.pack_into(RECORD_FORMAT, self._shm.buf, offset, order_id, float(price), quantity, side_code)
            self._set_indices(read_index, next_index)

    def read_order(self):
        """Read and return the oldest order as a dictionary, or None if empty."""
        with self._lock:
            _, _, capacity, read_index, write_index = self._header()
            if self._is_empty(read_index, write_index):
                return None
            offset = HEADER_SIZE + read_index * RECORD_SIZE
            order_id, price, quantity, side_code = struct.unpack_from(
                RECORD_FORMAT, self._shm.buf, offset
            )
            self._set_indices((read_index + 1) % capacity, write_index)
        if side_code not in (BUY, SELL):
            raise ValueError("corrupt side code in shared order buffer")
        return {
            "order_id": order_id,
            "price": price,
            "quantity": quantity,
            "side": "BUY" if side_code == BUY else "SELL",
        }

    def close(self) -> None:
        if not self._closed:
            self._shm.close()
            self._closed = True

    def unlink(self) -> None:
        """Remove the shared-memory segment; call once from the owner process."""
        if not self._owner:
            raise RuntimeError("only the creating process may unlink the buffer")
        self._shm.unlink()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

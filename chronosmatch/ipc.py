"""Fixed-record mmap ring buffer for sharing orders between processes."""
from __future__ import annotations

import math
import mmap
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from .orders import Side


_MAGIC = b"CHRONOS1"
_VERSION = 1
_HEADER = struct.Struct("<8sIIIII")
_RECORD = struct.Struct("<QdIB3xQ")
_SIDE_TO_CODE = {Side.BUY: 1, Side.SELL: 2}
_CODE_TO_SIDE = {value: key for key, value in _SIDE_TO_CODE.items()}


@dataclass(frozen=True, slots=True)
class IpcOrder:
    order_id: int
    side: Side
    price: float
    quantity: int
    timestamp_ns: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.order_id, bool)
            or not isinstance(self.order_id, int)
            or not 0 <= self.order_id < 2**64
        ):
            raise ValueError("order_id must be an unsigned 64-bit integer")
        if not isinstance(self.side, Side):
            try:
                object.__setattr__(self, "side", Side(str(self.side).upper()))
            except ValueError:
                raise ValueError("side must be BUY or SELL") from None
        try:
            price_is_finite = math.isfinite(self.price)
        except (OverflowError, TypeError):
            price_is_finite = False
        if (
            isinstance(self.price, bool)
            or not isinstance(self.price, (int, float))
            or not price_is_finite
            or self.price <= 0
        ):
            raise ValueError("price must be a positive finite number")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, int)
            or not 1 <= self.quantity < 2**32
        ):
            raise ValueError("quantity must be a positive unsigned 32-bit integer")
        if (
            isinstance(self.timestamp_ns, bool)
            or not isinstance(self.timestamp_ns, int)
            or not 0 <= self.timestamp_ns < 2**64
        ):
            raise ValueError("timestamp_ns must be an unsigned 64-bit integer")


class MmapRingBuffer:
    """Bounded ring buffer; all readers and writers must share one process lock."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        capacity: int,
        lock: Any,
        *,
        create: bool = False,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.path = Path(path)
        self.capacity = capacity
        self.lock = lock
        self._file = None
        self._mapping: Optional[mmap.mmap] = None

        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self.path.open("w+b")
            self._file.truncate(_HEADER.size + capacity * _RECORD.size)
            self._mapping = mmap.mmap(self._file.fileno(), 0)
            _HEADER.pack_into(
                self._mapping, 0, _MAGIC, _VERSION, capacity, 0, 0, 0
            )
        else:
            self._file = self.path.open("r+b")
            expected_size = _HEADER.size + capacity * _RECORD.size
            if os.fstat(self._file.fileno()).st_size != expected_size:
                self._file.close()
                self._file = None
                raise ValueError("mmap file size does not match the requested capacity")
            self._mapping = mmap.mmap(self._file.fileno(), 0)
            magic, version, stored_capacity, _, _, _ = _HEADER.unpack_from(
                self._mapping
            )
            if (magic, version, stored_capacity) != (_MAGIC, _VERSION, capacity):
                self.close()
                raise ValueError("mmap file header is invalid or has a different capacity")

    @classmethod
    def create(
        cls, path: str | os.PathLike[str], capacity: int, lock: Any
    ) -> "MmapRingBuffer":
        return cls(path, capacity, lock, create=True)

    @property
    def _map(self) -> mmap.mmap:
        if self._mapping is None:
            raise ValueError("ring buffer is closed")
        return self._mapping

    def _header(self) -> tuple[bytes, int, int, int, int, int]:
        header = _HEADER.unpack_from(self._map)
        magic, version, capacity, read_at, write_at, count = header
        if (
            magic != _MAGIC
            or version != _VERSION
            or capacity != self.capacity
            or not 0 <= read_at < capacity
            or not 0 <= write_at < capacity
            or not 0 <= count <= capacity
        ):
            raise RuntimeError("mmap ring buffer header is invalid")
        return header

    def put(self, order: IpcOrder) -> bool:
        return self.put_many((order,)) == 1

    def put_many(self, orders: Sequence[IpcOrder]) -> int:
        if not orders:
            return 0
        if any(not isinstance(order, IpcOrder) for order in orders):
            raise TypeError("all records must be IpcOrder instances")
        written = 0
        with self.lock:
            magic, version, capacity, read_at, write_at, count = self._header()
            written = min(capacity - count, len(orders))
            for order in orders[:written]:
                offset = _HEADER.size + write_at * _RECORD.size
                _RECORD.pack_into(
                    self._map,
                    offset,
                    order.order_id,
                    order.price,
                    order.quantity,
                    _SIDE_TO_CODE[order.side],
                    order.timestamp_ns,
                )
                write_at = (write_at + 1) % capacity
            if written:
                _HEADER.pack_into(
                    self._map,
                    0,
                    magic,
                    version,
                    capacity,
                    read_at,
                    write_at,
                    count + written,
                )
        return written

    def get(self) -> Optional[IpcOrder]:
        orders = self.get_many(1)
        return orders[0] if orders else None

    def get_many(self, max_items: int) -> list[IpcOrder]:
        if (
            isinstance(max_items, bool)
            or not isinstance(max_items, int)
            or max_items <= 0
        ):
            raise ValueError("max_items must be a positive integer")
        orders = []
        with self.lock:
            magic, version, capacity, read_at, write_at, count = self._header()
            for _ in range(min(count, max_items)):
                offset = _HEADER.size + read_at * _RECORD.size
                order_id, price, quantity, side_code, timestamp_ns = (
                    _RECORD.unpack_from(self._map, offset)
                )
                try:
                    side = _CODE_TO_SIDE[side_code]
                except KeyError:
                    raise RuntimeError(
                        "mmap ring buffer contains an invalid side code"
                    ) from None
                orders.append(
                    IpcOrder(order_id, side, price, quantity, timestamp_ns)
                )
                read_at = (read_at + 1) % capacity
            if orders:
                _HEADER.pack_into(
                    self._map,
                    0,
                    magic,
                    version,
                    capacity,
                    read_at,
                    write_at,
                    count - len(orders),
                )
        return orders

    def __len__(self) -> int:
        with self.lock:
            return self._header()[-1]

    def close(self) -> None:
        if self._mapping is not None:
            self._mapping.close()
            self._mapping = None
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> "MmapRingBuffer":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

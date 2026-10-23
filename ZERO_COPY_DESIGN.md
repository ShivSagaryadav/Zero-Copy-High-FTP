# Zero-Copy Optimization: Initial Design

## Scope

This branch currently contains only the project README. This contribution adds a
standalone shared-memory prototype without replacing `ring_buffer.py` or changing
the simulator interface used by other team members.

## Record format

The prototype uses a fixed 24-byte record encoded with `struct` format `<QdIB3x`:

| Field | Encoding | Size |
|---|---|---:|
| `order_id` | unsigned 64-bit integer | 8 bytes |
| `price` | IEEE-754 double | 8 bytes |
| `quantity` | unsigned 32-bit integer | 4 bytes |
| `side` | `0 = BUY`, `1 = SELL` | 1 byte |
| reserved padding | three bytes | 3 bytes |
| **Total** | | **24 bytes** |

The current team's `ring_buffer.py` record format is `<QdI` (20 bytes) and does
not store BUY/SELL side. Do not replace that interface until the team agrees on
the shared order schema.

## IPC approach

`shared_order_buffer.py` uses `multiprocessing.shared_memory.SharedMemory`.
Processes attach by shared-memory name and use the same `multiprocessing.Lock`.
This is a correctness-first prototype; the lock protects the shared indices and
record operations. It is not a lock-free queue.

The ring reserves one slot to distinguish full from empty. Therefore a buffer
created with capacity `N` can hold `N - 1` orders.

## Validation

Run:

```bash
python -m unittest -v test_shared_order_buffer.py
```

The tests cover record size, field validation, FIFO behavior, full/empty state,
wraparound, and a child process writing an order visible to the parent.

## Integration notes

- Keep this prototype separate from `ring_buffer.py` until the matching engine
  and order-management interfaces are agreed.
- Share the `SharedOrderBuffer` instance's `name` and the same multiprocessing
  lock with producer/consumer processes.
- Only the creating process should call `unlink()`, exactly once.
- Benchmark only after correctness tests pass. Report workload, Python version,
  machine, orders/second, and latency; do not claim a performance improvement
  without measurements.

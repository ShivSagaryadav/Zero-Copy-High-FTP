# ChronosMatch

ChronosMatch is an educational low-latency order-matching project for the
`matching-engine` branch. It combines a price-time-priority order book,
fixed-record memory-mapped IPC, an asynchronous market firehose, an optional
Cython matching kernel, latency metrics, a curses dashboard, and an asynchronous
SQLite trade ledger.

The project is a prototype, not a production HFT system. Python scheduling,
process locks, the operating system, and hardware all affect latency; no
sub-50-microsecond execution guarantee is made.

## Architecture

- `chronosmatch/matching_engine.py` matches marketable orders at the resting
  order price. Same-price orders follow arrival order.
- `chronosmatch/ipc.py` stores orders in a bounded mmap ring using fixed-width
  binary records. Processes must receive the same `multiprocessing.Lock`.
  Orders travel through mmap rather than being serialized through a queue.
- `chronosmatch/market.py` provides a seeded asynchronous mock firehose and an
  optional WebSocket JSON feed.
- `chronosmatch/_cython_matcher.pyx` contains a typed, GIL-free matching kernel.
  The Python implementation is always available as a fallback.
- `chronosmatch/metrics.py` tracks end-to-end monotonic latency percentiles and
  rolling throughput.
- `chronosmatch/dashboard.py` renders the order book and highlights large
  trades in a curses terminal UI.
- `chronosmatch/ledger.py` batches matched trades into SQLite asynchronously.
- `chronosmatch/pipeline.py` runs the firehose and matcher in separate
  processes, connects them with mmap, and persists trades.

## Install and run

From the repository root, using Python 3.10 or later:

```powershell
python -m pip install -r requirements.txt
python -m pytest
python -m chronosmatch
```

Run the end-to-end, separate-process pipeline:

```powershell
python -m chronosmatch pipeline --count 10000 --ledger chronosmatch_trades.sqlite3
```

Run the two-process mmap audit. It sends one million fixed-size records by
default; the count can be reduced for a quick check:

```powershell
python -m chronosmatch ipc-audit --count 1000000
```

Benchmark the end-to-end firehose, IPC, matcher, and trade-ledger pipeline:

```powershell
python benchmark.py --count 10000 --runs 5
```

The pipeline writes its SQLite ledger to `chronosmatch_trades.sqlite3` by
default. Pass `--ipc-file` to retain the mmap file instead of using a temporary
file. The IPC file is initialized on each run.

## Optional features

Build the native Cython matching extension:

```powershell
python -m pip install -r requirements-cython.txt
python setup_cython.py build_ext --inplace
```

On Windows, a compatible Microsoft C++ Build Tools installation is also
required. Without the native compiler, ChronosMatch continues to run using the
tested Python matcher.

Install the optional WebSocket client dependency with
`python -m pip install -r requirements-websocket.txt`. WebSocket messages are
JSON objects containing `order_id`, `side` (`BUY`/`SELL`), `price`, and
`quantity`. The pipeline can ingest a fixed number of those messages:

```powershell
python -m chronosmatch pipeline --websocket-url ws://localhost:8765/orders --count 10000
```

Remote event timestamps are ignored; local monotonic receive timestamps are
used for latency measurements.

Install the terminal dashboard dependency with
`python -m pip install -r requirements-dashboard.txt` on Windows. Then run:

```powershell
python -m chronosmatch pipeline --count 10000 --dashboard
```

Press `q` to close the dashboard. Incoming orders at or above the default
quantity threshold of 1,000 are highlighted, including orders split into
multiple fills across price levels. Change the threshold with
`--whale-threshold`.

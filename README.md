# ChronosMatch

ChronosMatch is an educational low-latency order-matching prototype. It
integrates a Python/Cython limit order book, fixed-record mmap IPC, an asyncio
market simulator, latency metrics, a terminal dashboard, and a batched SQLite
trade ledger. It is not a production HFT system: process scheduling, locking,
Python object overhead, and hardware affect performance, so latency targets are
goals rather than guarantees.

## Requirements

- Python 3.10 or later (the current project environment is Python 3.14).
- Windows 10/11 and PowerShell are supported.
- `pytest` is required for tests.
- Cython and Microsoft C++ Build Tools are optional and only required for the
  compiled matching kernel.
- `windows-curses` and `websockets` are optional.

## Windows installation

Run these commands from the existing project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PowerShell may block virtual-environment activation due to its execution
policy. In that case, run the interpreter explicitly as
`.venv\Scripts\python.exe` rather than changing the machine-wide policy.

### Optional Cython build

Install **Visual Studio Build Tools** with the **Desktop development with C++**
workload (MSVC compiler and a Windows SDK), then open a new PowerShell window:

```powershell
python -m pip install -r requirements-cython.txt
python setup_cython.py build_ext --inplace
python -c "from chronosmatch import _matcher; print(_matcher.BACKEND)"
```

The final command should report `cython`. Without a working compiler, the
project uses the pure-Python matcher. If compilation fails, verify that the
Build Tools C++ workload and Windows SDK are installed and that the Python
architecture matches the compiler target.

Optional integrations:

```powershell
python -m pip install -r requirements-dashboard.txt
python -m pip install -r requirements-websocket.txt
```

## Architecture and modules

```text
async market simulator
    -> multiprocessing lock + fixed-record mmap ring
    -> matching worker process / per-symbol price-time order books
    -> bounded-window latency metrics
    -> asynchronous batched SQLite ledger
    -> dashboard snapshots (optional)
```

- `chronosmatch/orders.py`: validated limit/market orders, symbols, and order
  lifecycle states.
- `chronosmatch/order_book.py` and `matching_engine.py`: per-symbol price-time
  priority books, best prices, partial fills, cancellations, and resting-price
  trade execution.
- `chronosmatch/_python_matcher.py`: reference kernel.
- `chronosmatch/_cython_matcher.pyx`: optional typed Cython matching kernel;
  its inner loop releases the GIL.
- `chronosmatch/ipc.py`: bounded mmap ring with fixed-width binary order
  records. Records include order ID, monotonic timestamp, symbol, price,
  quantity, side, and order type. The producer publishes a record under the
  same multiprocessing lock that consumers hold while copying records, so a
  consumer cannot observe a partially published record. The mmap path does not
  serialize orders with JSON or Pickle.
- `chronosmatch/market.py` and `simulator.py`: seeded async mock traffic,
  configurable symbols/rate/market-order probability, deterministic simulated
  post-announcement order-flow bursts, and an optional JSON-over-WebSocket
  adapter. Only the optional external feed uses JSON.
- `chronosmatch/metrics.py`: `perf_counter_ns()` latency samples, min/max/mean,
  p50/p95/p99, and rolling throughput.
- `chronosmatch/dashboard.py`: curses display with book depth, throughput,
  latency percentiles, IPC wait, GC collection count, recent trades, and whale
  highlighting.
- `chronosmatch/ledger.py`: transactionally batched SQLite persistence,
  indexes, trade-history queries, and executed-volume queries.
- `chronosmatch/pipeline.py`: producer and matcher in separate processes,
  mmap transport, worker metrics, graceful ledger flush, and optional live
  dashboard updates.

Order IDs are unique for the lifetime of a matching-engine instance. Supported
symbols are 1-16 ASCII letters, digits, `.`, `_`, or `-`. Market orders execute
against available opposing liquidity at resting prices; any unfilled remainder
is not added to the book. Status values are `NEW`, `OPEN`, `PARTIALLY_FILLED`,
`FILLED`, and `CANCELLED`; an unknown ID reports `UNKNOWN`.

## Run the application

Run the standalone matching demo:

```powershell
python -m chronosmatch
```

Run the integrated simulator, mmap consumer, matching engine, and SQLite
ledger:

```powershell
python -m chronosmatch pipeline --count 10000 --ledger .\chronosmatch_trades.sqlite3
```

Configure symbols, simulator rate, market-order share, and mmap capacity:

```powershell
python -m chronosmatch pipeline `
  --count 100000 `
  --symbols AAPL,MSFT,NVDA `
  --rate 100000 `
  --market-order-probability 0.05 `
  --announcement-after 25000 `
  --announcement-market-order-probability 0.5 `
  --capacity 4096 `
  --ledger .\chronosmatch_trades.sqlite3
```

The simulator rate is an upper pacing target; the machine and end-to-end
pipeline may not sustain it. Generated traffic waits for ring-buffer capacity,
so the local simulator does not silently drop orders. Result JSON reports
generated, published, and dropped counts. `--announcement-after` selects the
order number where a simulated earnings-news burst begins; after that point,
the market-order probability switches to
`--announcement-market-order-probability`.

Start the live dashboard (requires the optional Windows curses dependency):

```powershell
python -m chronosmatch pipeline --count 100000 --symbols AAPL,MSFT --dashboard
```

Press `q` to close the dashboard. Use `--whale-threshold 1000` to configure the
quantity threshold. The pipeline prints final metrics after completion.

An optional WebSocket server may send order objects with `order_id`, `side`,
`price`, `quantity`, and optional `symbol` and `order_type`. Market-order
messages may omit `price`; remote timestamps are ignored in favor of local
monotonic timestamps:

```powershell
python -m chronosmatch pipeline `
  --websocket-url ws://localhost:8765/orders `
  --count 10000 `
  --ledger .\websocket_trades.sqlite3
```

## Testing

From the project directory:

```powershell
python -m pytest -q
```

The tests cover the order book and matching lifecycle, Python/native matcher
API, mmap wraparound and cross-process audit, simulator, latency metrics,
SQLite persistence/migrations, dashboard rendering, WebSocket ingestion, and
the end-to-end pipeline.

The dated daily workflow from 15-10-2026 through 02-11-2026 is documented in
[PROJECT_WORKFLOW.md](./PROJECT_WORKFLOW.md). It is organized into four
sections, with partial first and final weeks to match the requested dates.

## IPC audit and performance benchmarks

The IPC audit transfers one million records between separate processes by
default and validates the final checksum:

```powershell
python -m chronosmatch ipc-audit --count 1000000
```

Use `--count 1000` for a quick smoke test or `--timeout 600` for a slower
machine. The benchmark defaults to at least 100,000 end-to-end orders and
reports engine-only and end-to-end percentiles plus Python/Cython kernel call
rates:

```powershell
python benchmark.py
python benchmark.py --count 100000 --runs 3
```

All reported values are measured on the machine running the command. No
performance result is guaranteed; the matching-engine target is below 50
microseconds and the end-to-end target is below one millisecond where hardware
and operating-system conditions permit.

## SQLite ledger

Trades are inserted asynchronously in batches and committed as SQLite
transactions. Existing ledgers are migrated to include symbols and order-size
metadata. Indexes support symbol/time history and order-ID lookups. The
`AsyncTradeLedger.trade_history(symbol=..., limit=...)` and
`AsyncTradeLedger.total_executed_volume(symbol=...)` methods query persisted
records. A normal SQLite transaction rollback protects an incomplete batch;
SQLite recovery handles journal/WAL recovery after process interruption.

## Known limitations

- This is a local educational prototype, not an exchange gateway or
  production-grade trading system.
- The process-shared lock favors correctness; lock contention and Python
  scheduling can limit throughput and tail latency.
- The Cython kernel accelerates the fill calculation, but order-book updates,
  Python object handling, SQLite, and IPC still contribute to total latency.
- The dashboard is a terminal interface and requires `windows-curses` on
  Windows. Its visible order book follows the most recently processed symbol.
- A crashed producer/consumer requires a fresh initialized mmap file for the
  next run; use `--ipc-file` only when intentionally managing that lifecycle.
- SQLite persistence is single-writer. ClickHouse and production recovery/
  replication are not implemented.

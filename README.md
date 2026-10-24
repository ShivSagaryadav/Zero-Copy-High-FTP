Zero-Copy-High-FTP

# ChronosMatch - High-Performance Order Matching Engine

ChronosMatch is a Python-based project for developing an order-matching engine for high-frequency trading. It aims to explore efficient order handling, price-time priority matching, memory-mapped ring buffers, and performance benchmarking.

## Project Objectives

1. Implement an order book for buy and sell orders.
2. Match orders using price-time priority.
3. Explore efficient data handling using memory-mapped storage and other zero-copy techniques.
4. Measure latency and throughput.
5. Compare the basic implementation with optimized versions.

## Project Modules

- **Order Management:** Create and validate orders.
- **Matching Engine:** Implement order-book operations and price-time priority matching.
- **Zero-Copy Optimization:** Explore memory-mapped ring buffers and other data-handling techniques.
- **Testing and Benchmarking:** Verify correctness and measure performance.

## Technology Stack

- Python
- `mmap` and `struct`
- Git and GitHub
- Python `unittest`

## Current Implementation

- Order creation and input validation in `orders.py`.
- Memory-mapped ring buffer implementation in `ring_buffer.py`.
- Automated order tests in `test_orders.py`.
- Automated ring buffer tests in `test_ring_buffer.py`.

The project is under development. Cross-process communication, matching-engine integration, and performance targets must be verified separately as implementation progresses.

## Setup

Use Python 3.10 or later.

Clone the repository and open its project directory:

```bash
git clone https://github.com/ShivSagaryadav/Zero-Copy-High-FTP.git
cd Zero-Copy-High-FTP
```

## Run the Tests

Run all automated tests:

```bash
python -m unittest -v
```

Run order validation tests only:

```bash
python -m unittest -v test_orders.py
```

Run ring buffer tests only:

```bash
python -m unittest -v test_ring_buffer.py
```

## Expected Outcome

A modular order-matching engine with verified matching logic and benchmark results comparing the basic and optimized implementations.

## Asynchronous Order Simulator

Run the simulator using `python async_simulator.py`. It asynchronously generates and consumes 10,000 mock orders using the memory-mapped ring buffer. The reported generation rate measures the producer generation/write-loop, not end-to-end matching-engine throughput. The current ring buffer stores order ID, price, and quantity, but not BUY/SELL side.


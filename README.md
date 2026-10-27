Zero-Copy-High-FTP

ChronosMatch — High-Performance Order Matching Engine
ChronosMatch is a Python-based high-frequency trading order-matching engine designed to match buy and sell orders efficiently using price-time priority. The project explores zero-copy techniques, including memoryview, shared memory, and ring buffers, to reduce data-copying overhead and improve performance.

Project Objectives
1.Implement an order book for buy and sell orders.
2.Match orders using price-time priority.
3.Explore zero-copy data handling techniques.
4.Measure latency and throughput.
5.Compare the optimized implementation with a basic baseline.

Project Modules
1.Order Management: Create, validate, and manage orders.
2.Matching Engine: Implement order-book operations and price-time priority matching.
3.Zero-Copy Optimization: Explore memory view, shared memory, and ring buffers.
4.Testing and Benchmarking: Test correctness and compare performance.

Technology Stack
1.Python
2.Git and GitHub
3.Python testing tools
4.Shared memory and memory view
5.Performance benchmarking tools

Project Status
Currently under development.

Expected Outcome

A modular order-matching engine with tested matching logic and benchmark results comparing the basic and optimized implementations.

## Run

From the repository root:

```powershell
python -m pytest
python -m chronosmatch
```

The matching-engine copy can also be run independently:

```powershell
Set-Location matching-engine
python -m pytest
python -m chronosmatch
```

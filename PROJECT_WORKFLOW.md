# ChronosMatch Daily Project Workflow

## Date range and reporting rule

- Requested range: **15-10-2026 through 02-11-2026** (current date).
- The request also mentions **12-10-2026**, but gives **15-10-2026** as the
  starting date. This workflow uses the explicit start date, 15 October.
- To keep the requested four week sections within the date range, Week 1 is a
  partial week, Weeks 2 and 3 are full weeks, and Week 4 contains the current
  day only.
- This is a dated execution workflow and reporting template, not proof that
  every activity was historically performed on its listed date. Add actual
  notes and evidence as each day's work is completed; do not backdate new work.

## Week 1 — Project discovery and core design

| Date | Daily focus | Work and expected evidence |
|---|---|---|
| Thu, 15-10-2026 | Project kickoff | Confirm project scope, Python/Windows environment, existing repository structure, and acceptance criteria. Record the active project root and preserve existing files. |
| Fri, 16-10-2026 | Existing implementation review | Inspect the order model, order book, matching engine, IPC, simulator, persistence, dashboard, and tests. List gaps without replacing working modules. |
| Sat, 17-10-2026 | Data model and order lifecycle | Define validated order fields, symbols, sides, limit/market types, and lifecycle states. Add focused validation and status tests. |
| Sun, 18-10-2026 | Matching-engine design | Confirm price-time priority, resting-price execution, partial fills, cancellation rules, and order-ID uniqueness. Write representative matching test cases. |

## Week 2 — Matching engine, IPC, and market simulation

| Date | Daily focus | Work and expected evidence |
|---|---|---|
| Mon, 19-10-2026 | Python matching reference | Implement or complete the Python matching path; verify best bid/ask, multiple levels, partial fills, and trade quantities. |
| Tue, 20-10-2026 | Cython matcher | Implement the typed matching kernel, build it with the available Windows C++ toolchain, and compare its output with the Python reference. |
| Wed, 21-10-2026 | mmap record format | Define the fixed-size binary order record, including ID, price, quantity, side, timestamp, symbol, and order type. Verify field validation and round trips. |
| Thu, 22-10-2026 | Ring-buffer correctness | Implement bounded writes/reads, wraparound, empty/full behavior, shared-lock synchronization, and protection from reading unpublished records. |
| Fri, 23-10-2026 | Cross-process IPC | Exercise producer and consumer processes using the same mmap file and lock. Check ordering, record count, and checksum. |
| Sat, 24-10-2026 | Async market simulator | Add repeatable multi-symbol order generation, configurable pacing, market-order traffic, and a post-announcement burst option. |
| Sun, 25-10-2026 | IPC and simulator regression tests | Run focused ring-buffer and simulator tests; record generated, published, consumed, and dropped order counts. Resolve failures before integration. |

## Week 3 — Persistence, telemetry, integration, and benchmarks

| Date | Daily focus | Work and expected evidence |
|---|---|---|
| Mon, 26-10-2026 | SQLite trade ledger | Implement schema creation/migration, indexed trade storage, transactional batch writes, history lookup, and executed-volume queries. Verify persisted records. |
| Tue, 27-10-2026 | Latency metrics | Measure monotonic timestamps for publication, consumption, matching, and end-to-end processing. Report min/max/mean and p50/p95/p99 without inventing results. |
| Wed, 28-10-2026 | End-to-end backend | Connect simulator → mmap → consumer → matcher → ledger. Confirm shutdown flushes pending trades and reports worker failures. |
| Thu, 29-10-2026 | Dashboard integration | Display the active symbol's book, recent trades, throughput, latency percentiles, IPC wait, GC activity, and whale-order highlighting. Test refresh and quit behavior. |
| Fri, 30-10-2026 | Integration and failure-path tests | Run the full test suite, including websocket input where installed. Check pipeline shutdown, ledger persistence, empty input, and bounded ring behavior. |
| Sat, 31-10-2026 | Native build and parity | Force a fresh Cython extension build, verify the selected backend, and run Python-versus-Cython equivalence tests. |
| Sun, 01-11-2026 | Performance measurement | Run the 100,000-order benchmark and one-million-record IPC audit. Capture machine/runtime, throughput, latency percentiles, checksum, and whether each target was met. |

## Week 4 — Final verification and handoff

| Date | Daily focus | Work and expected evidence |
|---|---|---|
| Mon, 02-11-2026 | Final review and handoff | Re-run the complete tests after the latest integration fix; verify CLI startup and a live pipeline run with trades stored in SQLite. Update benchmark measurements, README instructions, known limitations, and this workflow with actual results. |

## Daily update format

Append a short entry after completing each day's work:

```text
Date:
Planned focus:
Completed:
Files or modules changed:
Validation command(s):
Observed result:
Blockers or follow-up:
```

Keep dates in `DD-MM-YYYY` format. If the task moves to another date, record
the actual completion date rather than changing the scheduled date or claiming
an unverified result.

## Current verified checkpoint

The current project checkpoint has a passing full test suite (**69 passed, 6
subtests passed**) and a successfully built Cython extension on the Windows
environment. The latest recorded performance measurements and limitations are
in [BENCHMARK_RESULTS.md](./BENCHMARK_RESULTS.md). In particular, observed
end-to-end latency did not meet the one-millisecond goal; benchmark targets
must remain clearly distinguished from measured results.

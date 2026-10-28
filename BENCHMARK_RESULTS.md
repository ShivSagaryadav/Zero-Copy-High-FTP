# ChronosMatch Benchmark Results

These are local prototype measurements, not latency or throughput guarantees.
Repeat the tests on the target machine with `python benchmark.py` and
`python -m chronosmatch ipc-audit --count 1000000`.

## Mmap IPC audit

| Date | Records | Result | Throughput |
|---|---:|---|---:|
| 2026-10-27 | 1,000,000 | All records consumed; checksum matched | 186,944 records/s total |
| 2026-10-27 | 1,000,000 | Async producer enqueue rate | 187,680 records/s |

This two-process test transfers fixed-size mmap records; it does not pickle
orders. The measured IPC rate exceeded the 100,000-records/s firehose target on
the development machine.

## End-to-end pipeline

Run `python benchmark.py --count 10000 --runs 5` to measure the complete
firehose, mmap, matching, and SQLite path. The script reports throughput,
end-to-end latency, p99 latency, and in-engine latency for the active matcher.
Latency is reported from local `perf_counter_ns()` measurements.

One 10,000-order end-to-end run on the development machine reported 31,692
orders/s total processing throughput, 13,734 microseconds average and 23,129
microseconds p99 end-to-end latency. The in-engine measurement was 4.88
microseconds average and 19.30 microseconds p99. These figures vary by run and
machine; they are not production guarantees.

The Python matcher was measured because the development machine does not have
Microsoft C++ Build Tools. Cython source translation passed, but building the
native extension requires the compiler documented in the README.

## Validation

- Root project tests: 40 passed (plus 6 parameterized input cases).
- End-to-end pipeline test: generated orders were consumed in another process
  and matched trades were written to SQLite.

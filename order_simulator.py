
import asyncio

from chronosmatch.simulator import MockOrder, generate_orders, run_simulation


if __name__ == "__main__":
    results = asyncio.run(run_simulation())

    print("\nChronosMatch - Initial Simulator Benchmark")
    print("-" * 45)

    for name, value in results.items():
        print(f"{name}: {value}")

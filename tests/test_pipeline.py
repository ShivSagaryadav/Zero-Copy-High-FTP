import asyncio
import sqlite3

from chronosmatch.pipeline import run_pipeline


def test_pipeline_ingests_matches_and_persists_in_separate_process(tmp_path):
    updates = []

    async def run():
        return await run_pipeline(
            100,
            capacity=8,
            ledger_path=tmp_path / "pipeline.sqlite3",
            process_timeout=30,
            on_state=updates.append,
        )

    ledger_path = tmp_path / "pipeline.sqlite3"
    result = asyncio.run(run())
    assert result["firehose"]["produced"] == 100
    assert result["consumed"] == 100
    assert result["latency"]["samples"] == 100
    assert result["engine_latency"]["observations"] == 100
    assert result["engine_latency"]["average_latency_us"] >= 0
    assert result["matcher_backend"] in {"python", "cython"}
    assert updates
    assert updates[-1]["engine_latency_us"] >= 0
    assert result["processing_elapsed_seconds"] > 0
    assert result["processing_throughput_orders_per_second"] > 0
    with sqlite3.connect(ledger_path) as connection:
        trade_count = connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    assert trade_count == result["trade_count"]

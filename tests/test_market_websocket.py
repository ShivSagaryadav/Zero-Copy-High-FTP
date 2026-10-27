import asyncio
import json
import sqlite3

import pytest

websockets = pytest.importorskip("websockets")

from chronosmatch.pipeline import run_pipeline


def test_websocket_orders_feed_the_separate_process_pipeline(tmp_path):
    async def verify():
        async def handler(websocket, *args):
            for order_id in range(1, 21):
                await websocket.send(
                    json.dumps(
                        {
                            "order_id": order_id,
                            "side": "SELL" if order_id % 2 else "BUY",
                            "price": 100.0,
                            "quantity": 1,
                        }
                    )
                )

        server = await websockets.serve(handler, "127.0.0.1", 0)
        try:
            port = server.sockets[0].getsockname()[1]
            ledger_path = tmp_path / "websocket-trades.sqlite3"
            result = await run_pipeline(
                20,
                capacity=8,
                ledger_path=ledger_path,
                websocket_url=f"ws://127.0.0.1:{port}",
                process_timeout=30,
            )
            assert result["consumed"] == 20
            assert result["firehose"]["produced"] == 20
            with sqlite3.connect(ledger_path) as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM trades"
                ).fetchone()[0]
            assert count == result["trade_count"] > 0
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(verify())

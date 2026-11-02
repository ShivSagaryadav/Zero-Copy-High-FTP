from __future__ import annotations

import argparse
import asyncio
import json

from . import MatchingEngine, Order
from .dashboard import DashboardState, run_curses_dashboard
from .ipc_audit import run_ipc_audit
from .pipeline import run_pipeline


def _demo() -> None:
    engine = MatchingEngine()
    engine.submit(Order("S1", "SELL", 100.5, 6))
    engine.submit(Order("S2", "SELL", 101.0, 5))
    for trade in engine.submit(Order("B1", "BUY", 101.0, 10)):
        print(
            f"TRADE #{trade.trade_id}: buy {trade.buy_order_id} / "
            f"sell {trade.sell_order_id} {trade.quantity} @ {trade.price} "
            f"= {trade.value} ({trade.latency_ns} ns)"
        )
    print("Matcher:", engine.matcher_backend)
    print("Spread:", engine.book.spread(), "| Book:", engine.book.snapshot())
    print("B1 status:", engine.status("B1"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chronosmatch",
        description="ChronosMatch low-latency matching and IPC tools",
    )
    subparsers = parser.add_subparsers(dest="command")
    pipeline = subparsers.add_parser(
        "pipeline", help="run the async firehose and separate-process matcher"
    )
    pipeline.add_argument("--count", type=int, default=10_000)
    pipeline.add_argument("--seed", type=int, default=42)
    pipeline.add_argument("--capacity", type=int, default=1024)
    pipeline.add_argument("--ledger", default="chronosmatch_trades.sqlite3")
    pipeline.add_argument("--ipc-file")
    pipeline.add_argument("--websocket-url")
    pipeline.add_argument("--dashboard", action="store_true")
    pipeline.add_argument("--whale-threshold", type=int, default=1_000)

    audit = subparsers.add_parser(
        "ipc-audit", help="audit mmap IPC with two processes (default: 1M orders)"
    )
    audit.add_argument("--count", type=int, default=1_000_000)
    audit.add_argument("--capacity", type=int, default=4096)
    audit.add_argument("--timeout", type=float, default=300.0)
    return parser


async def _run_pipeline(args: argparse.Namespace) -> None:
    current = DashboardState([], [], None, 0.0, 0.0, 0.0, [])

    def update_state(data: dict) -> None:
        nonlocal current
        current = DashboardState(**data)

    pipeline_task = asyncio.create_task(
        run_pipeline(
            args.count,
            seed=args.seed,
            capacity=args.capacity,
            ledger_path=args.ledger,
            ipc_path=args.ipc_file,
            websocket_url=args.websocket_url,
            on_state=update_state,
        )
    )
    if args.dashboard:
        try:
            await asyncio.to_thread(
                run_curses_dashboard,
                lambda: current,
                whale_threshold=args.whale_threshold,
            )
        except Exception:
            pipeline_task.cancel()
            await asyncio.gather(pipeline_task, return_exceptions=True)
            raise
    result = await pipeline_task
    print(json.dumps(result, indent=2))


def main() -> None:
    args = _parser().parse_args()
    if args.command is None:
        _demo()
    elif args.command == "pipeline":
        asyncio.run(_run_pipeline(args))
    elif args.command == "ipc-audit":
        print(json.dumps(run_ipc_audit(
            args.count, capacity=args.capacity, timeout=args.timeout
        ), indent=2))


if __name__ == "__main__":
    main()

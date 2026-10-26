from chronosmatch import Order, MatchingEngine

engine = MatchingEngine()

engine.submit(Order("S1", "SELL", 100.5, 6))
engine.submit(Order("S2", "SELL", 101.0, 5))

trades = engine.submit(Order("B1", "BUY", 101.0, 10))

for trade in trades:
    print(
        f"TRADE #{trade.trade_id}: "
        f"buy {trade.buy_order_id} / sell {trade.sell_order_id} "
        f"{trade.quantity} @ {trade.price} = {trade.value}"
    )

print("Spread:", engine.book.spread())
print("Book snapshot:", engine.book.snapshot())
print("B1 status:", engine.status("B1"))
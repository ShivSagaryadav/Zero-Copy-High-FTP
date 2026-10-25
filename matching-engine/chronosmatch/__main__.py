from .matching_engine import MatchingEngine
from .orders import Order

e = MatchingEngine()
e.submit(Order("S1", "SELL", 100.5, 6))
e.submit(Order("S2", "SELL", 101.0, 5))
for t in e.submit(Order("B1", "BUY", 101.0, 10)):
    print(f"TRADE #{t.trade_id}: buy {t.buy_order_id} / sell {t.sell_order_id} "
          f"{t.quantity} @ {t.price} = {t.value}")
print("Spread:", e.book.spread(), "| Book:", e.book.snapshot())
print("B1 status:", e.status("B1"))

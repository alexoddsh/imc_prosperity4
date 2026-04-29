"""Per-trader realised + mark-to-market P&L, split by maker vs taker side.
Maker = bought below mid / sold above mid (got a passive fill).
Taker = bought above mid / sold below mid (crossed the spread).
A trader is replicable iff their *taker* P&L is positive — that's directional
alpha that survives queue position. Maker P&L is just spread capture.
"""
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "backtester" / "resources-4" / "round4"
DAYS = [1, 2, 3]


def day_pnl(day: int) -> pd.DataFrame:
    trades = pd.read_csv(ROOT / f"trades_round_4_day_{day}.csv", sep=";")
    prices = pd.read_csv(ROOT / f"prices_round_4_day_{day}.csv", sep=";")

    final_mid = (
        prices.sort_values("timestamp")
        .groupby("product")["mid_price"]
        .last()
        .to_dict()
    )
    mid_lookup = prices.set_index(["timestamp", "product"])["mid_price"].to_dict()

    # (trader, product, side) -> cash / pos
    cash: dict[tuple[str, str, str], float] = defaultdict(float)
    pos: dict[tuple[str, str, str], int] = defaultdict(int)

    for t in trades.itertuples(index=False):
        notional = t.price * t.quantity
        mid = mid_lookup.get((t.timestamp, t.symbol))

        if isinstance(t.buyer, str) and t.buyer:
            # buyer above mid -> taker; below -> maker; at mid -> maker (conservative)
            side = "taker" if mid is not None and t.price > mid else "maker"
            cash[(t.buyer, t.symbol, side)] -= notional
            pos[(t.buyer, t.symbol, side)] += t.quantity
        if isinstance(t.seller, str) and t.seller:
            side = "taker" if mid is not None and t.price < mid else "maker"
            cash[(t.seller, t.symbol, side)] += notional
            pos[(t.seller, t.symbol, side)] -= t.quantity

    rows = []
    for (trader, product, side), c in cash.items():
        p = pos[(trader, product, side)]
        mtm = p * final_mid.get(product, 0)
        rows.append({
            "day": day, "trader": trader, "product": product, "side": side,
            "pnl": round(c + mtm, 1), "end_pos": p,
        })
    return pd.DataFrame(rows)


def main() -> None:
    df = pd.concat([day_pnl(d) for d in DAYS], ignore_index=True)

    by_trader_side = (
        df.groupby(["trader", "side"])["pnl"].sum().unstack(fill_value=0).round(0)
    )
    by_trader_side["total"] = by_trader_side.sum(axis=1)
    by_trader_side = by_trader_side.sort_values("total", ascending=False)
    print("=== P&L by trader split by side (sum across products & days) ===")
    print(by_trader_side.to_string())
    print()

    # Per-product taker P&L — only positive values are replicable signal candidates
    taker = df[df["side"] == "taker"]
    taker_by_product = (
        taker.groupby(["trader", "product"])["pnl"].sum().unstack(fill_value=0).round(0)
    )
    taker_by_product["total_taker"] = taker_by_product.sum(axis=1)
    taker_by_product = taker_by_product.sort_values("total_taker", ascending=False)
    print("=== TAKER P&L by trader × product (replicable signal candidates) ===")
    print(taker_by_product.to_string())


if __name__ == "__main__":
    main()

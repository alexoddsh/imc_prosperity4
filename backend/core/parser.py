import pandas as pd
import io
import re
import json
from pathlib import Path
from database import fast_pg_insert, update_backtest_status
from core import classification, normalizer, position, inter


def process_results(task_id: str, log_path: Path, stream_log: Path) -> int:
    try:
        text = log_path.read_text()
        text2 = stream_log.read_text()

        ai = text.find("Activities log:\n")
        ti = text.find("Trade History:\n")
        id_lines = text2.splitlines()

        if ai == -1 or ti == -1:
            print("  [ERROR]: Could not find Activities log or Trade History ---")
            return

        #prices
        prices_str = text[ai + len("Activities log:\n"):ti].strip()
        prices = pd.read_csv(io.StringIO(prices_str), sep=";")
        final_pnl = float(prices["profit_and_loss"].iloc[-1])

        #trades
        time_to_day = dict(zip(prices['timestamp'], prices['day']))
        trade_str = text[ti + len("Trade History:\n"):].strip()
        trade_str = re.sub(r',\s*([}\]])', r'\1', trade_str)
        trades = pd.DataFrame(json.loads(trade_str))
        trades['day'] = trades['timestamp'].map(time_to_day)

        #internal data
        id={}
        day = -3
        i = 0
        for line in id_lines:
            if line.startswith("B"): #backtesting log
                day += 1
            elif line.strip().startswith("{"):
                id[(i, str(day))] = line.strip()
                i += 1
        
        internal = pd.DataFrame(columns=["timestamp", "product", "order_price", "order_quantity"])
        print("  [INTERNAL]: Internal parsing underway")
        success = inter.parse_internal(id, internal)
        if not success:
            raise Exception("  [INTERNAL]: Internal data parsing failed")
        
        #pre insert computations (prices)
        products = prices[prices["timestamp"] == 0]["product"].to_list()
        if len(products) == 0:
            raise ValueError("  [TRADES]: No products where found in the TDF")

        for product in products:
            print(f"  [WALLMID]: Wallmid Classes for {product}")
            success1 = normalizer.compute_wallmid1(product, prices)
            success2 = normalizer.compute_wallmid2(product, prices)
            if not success1 or not success2:
                raise Exception(f"  [WALLMID]: Pre compute failed {product}")

        #prev insert computations (trades)
        for product in products:
            print(f"  [CLASSIFICATION]: Calculating Classes for {product}")
            success = classification.compute_classes(product, prices, trades)
            if not success:
                raise Exception(f"  [CLASSIFICATION]: Pre compute failed {product}")
            print(f"  [POSITION]: Calculating position for {product}")
            success = position.compute_position(product, trades)
            if not success:
                raise Exception(f"  [POSITION]: Pre compute failed {product}")
            
        prices.insert(0, "backtest_id", str(task_id))
        trades.insert(0, "backtest_id", str(task_id))
        internal.insert(0, "backtest_id", str(task_id))

        fast_pg_insert(trades, "trades")
        fast_pg_insert(prices, "prices")
        fast_pg_insert(internal, "internal")
        update_backtest_status(str(task_id), "COMPLETED", final_pnl)

    except Exception as e:
        print(f"  [PARSER]: Parser Failed: {e}")
        update_backtest_status(str(task_id), "FAILED")
        return 0

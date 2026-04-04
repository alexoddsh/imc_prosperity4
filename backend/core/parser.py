from io import StringIO
import pandas as pd
import io
import re
import json
from pathlib import Path
from core.models import SystemEnum
from database import fast_pg_insert, update_backtest_status
from core import classification, normalizer, position, inter

def process_results(task_id: str, log_path: Path, stream_log: Path | None, system: SystemEnum) -> int:
    try:
        if system == SystemEnum.PROSPERITY4TBX:
            text = log_path.read_text()
            text2 = stream_log.read_text()
        
            ai = text.find("Activities log:\n")
            ti = text.find("Trade History:\n")
            id_lines = text2.splitlines()

            if ai == -1 or ti == -1:
                raise ValueError("  [ERROR]: Could not find Activities log or Trade History ---")

            #prices
            prices_str = text[ai + len("Activities log:\n"):ti].strip()
            prices = pd.read_csv(io.StringIO(prices_str), sep=";")
            
            #trades
            time_to_day = dict(zip(prices['timestamp'], prices['day']))
            trade_str = text[ti + len("Trade History:\n"):].strip()
            trade_str = re.sub(r',\s*([}\]])', r'\1', trade_str)
            trades = pd.DataFrame(json.loads(trade_str))
            trades['day'] = trades['timestamp'].map(time_to_day)

            #internal data
            ied={}
            day = -3
            i = 0
            for line in id_lines:
                if line.startswith("B"): #backtesting log
                    day += 1
                elif line.strip().startswith("{"):
                    ied[(i, str(day))] = line.strip()
                    i += 1
            
            internal = pd.DataFrame(columns=["timestamp", "product", "order_price", "order_quantity"])
            print("  [INTERNAL]: Internal parsing underway")
            success = inter.parse_internal(ied, internal)
            if not success:
                raise Exception("  [INTERNAL]: Internal data parsing failed")
        
        elif system == SystemEnum.PROSPERITY:
            #prices and trades 
            data = json.loads(log_path.read_text())
            ai = data["activitiesLog"]
            th = data["tradeHistory"]
            ied = data["logs"]

            if not ai or not th or not ied:
                raise ValueError("  [ERROR]: Could not find Activities log or Trade History ---")
            
            prices = pd.read_csv(StringIO(ai), sep=";")
            prices["day"] = 0
            trades = pd.DataFrame(th)
            trades["day"] = 0

            #internal 
            raw_logs = {}
            day = 0
            i = 0 #just acts like a fake index kinda

            for entry in ied:
                raw_logs[(i, day)] = entry["lambdaLog"]
                i += 1
            
            internal = pd.DataFrame(columns=["timestamp", "product", "order_price", "order_quantity"])
            print("  [INTERNAL]: Internal parsing underway")

            success = inter.parse_internal(raw_logs, internal)
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
        
        #pnl handling
        pnl = 0
        if system == SystemEnum.PROSPERITY4TBX:
            for product in products:
                pnl += prices[(prices["timestamp"] == 999900) & (prices["product"] == product)]["profit_and_loss"].item() + prices[(prices["timestamp"] == 1999900) & (prices["product"] == product)]["profit_and_loss"].item()
        elif system == SystemEnum.PROSPERITY:
            for product in products:
                pnl += prices[(prices["timestamp"] == 199900) & (prices["product"] == product)]["profit_and_loss"].item()

        prices.insert(0, "backtest_id", str(task_id))
        trades.insert(0, "backtest_id", str(task_id))
        internal.insert(0, "backtest_id", str(task_id))

        # Force ints (becomes floats because of NaNs)
        cols_to_fix = [
            'bid_price_1', 'bid_volume_1', 'bid_price_2', 'bid_volume_2', 'bid_price_3', 'bid_volume_3',
            'ask_price_1', 'ask_volume_1', 'ask_price_2', 'ask_volume_2', 'ask_price_3', 'ask_volume_3'
        ]

        for col in cols_to_fix:
            if col in prices.columns:
                prices[col] = prices[col].fillna(0).astype('int32')

        fast_pg_insert(trades, "trades")
        fast_pg_insert(prices, "prices")
        fast_pg_insert(internal, "internal")
        update_backtest_status(str(task_id), "COMPLETED", pnl)
        return 1

    except Exception as e:
        print(f"  [PARSER]: Parser Failed: {e}")
        update_backtest_status(str(task_id), "FAILED")
        return 0

import pandas as pd
import io
import re
from pathlib import Path
from database import fast_pg_insert, update_backtest_status

def process_results(task_id: str, log_path: Path):
    print(f"--- [PARSER]: Using Activities Log Extraction for {task_id} ---")
    try:
        text = log_path.read_text()
        
        # 1. Locate the "Activities log" section
        ai = text.find("Activities log:\n")
        ti = text.find("Trade History:\n")
        
        if ai == -1 or ti == -1:
            print("--- [ERROR]: Could not find Activities log section! ---")
            return

        # 2. Extract the table string
        # This is the CSV data between "Activities log" and "Trade History"
        table_str = text[ai + len("Activities log:\n"):ti].strip()
        
        # 3. Load into Pandas (It uses ';' as a separator)
        df_raw = pd.read_csv(io.StringIO(table_str), sep=";")
        
        if df_raw.empty:
            print("--- [ERROR]: Activities log is empty! ---")
            return

        # 4. Format for our Database
        df = pd.DataFrame()
        df['backtest_id'] = [str(task_id)] * len(df_raw)
        df['timestamp'] = df_raw['timestamp']
        df['product'] = df_raw['product']
        df['bid_price_1'] = pd.to_numeric(df_raw['bid_price_1'], errors='coerce')
        df['ask_price_1'] = pd.to_numeric(df_raw['ask_price_1'], errors='coerce')
        df['mid_price'] = pd.to_numeric(df_raw['mid_price'], errors='coerce')
        df['profit_and_loss'] = pd.to_numeric(df_raw['profit_and_loss'], errors='coerce')

        # 5. Get the Final PnL for the status update (last row of first product)
        first_product = df['product'].iloc[-1]
        last_rows = df[df['product'] == first_product]
        final_pnl = float(last_rows['profit_and_loss'].iloc[-1])

        # 6. Insert
        print(f"--- [SUCCESS]: Found {len(df)} rows in Activities Log ---")
        fast_pg_insert(df, "indicators")
        update_backtest_status(str(task_id), "COMPLETED", final_pnl)

    except Exception as e:
        print(f"!!! Parser Failed: {e}")
        update_backtest_status(str(task_id), "FAILED")
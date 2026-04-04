import pandas as pd
import json

def parse_internal(raw_logs: dict, intdf: pd.DataFrame) -> bool:
    rows = []

    try:
        for (i, day), row in raw_logs.items():
            entry = json.loads(row)
            raw_sandboxlog = entry["sandboxLog"].replace("[DATA] ", "")
            sandbox = json.loads(raw_sandboxlog)
            
            sandbox_day_keyed = {(day, key): value for key, value in sandbox.items()}
            
            for (day, timestamp), data_list, in sandbox_day_keyed.items():
                if day == str(-1):
                            timestamp = int(timestamp) + 1000000 
                for orders in data_list:
                    for order in orders:
                        if order[2] == 0:
                            continue
                        new_row = {
                            "timestamp": int(timestamp),
                            "product": order[0],
                            "order_price": order[1],
                            "order_quantity": order[2],
                            "day": day
                        }
                        rows.append(new_row)

        new_data = pd.DataFrame(rows)
        for col in new_data.columns:
            intdf[col] = new_data[col]

        return True
    
    except Exception as e:
        print(f"  [INTERNAL]: Something went wrong: {e}")
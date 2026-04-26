import pandas as pd
import json

def parse_internal(raw_logs: dict, intdf: pd.DataFrame) -> bool:
    rows = []

    try:
        for (i, day, day_index), row in raw_logs.items():
            if not row or not row.strip().startswith("{"):
                continue
            try:
                sandbox = json.loads(row)
            except json.JSONDecodeError:
                continue

            for timestamp_str, data_list in sandbox.items():
                abs_timestamp = int(timestamp_str) + day_index * 1000000
                for orders in data_list:
                    for order in orders:
                        if order[2] == 0:
                            continue
                        rows.append({
                            "timestamp": abs_timestamp,
                            "product": order[0],
                            "order_price": order[1],
                            "order_quantity": order[2],
                            "day": day
                        })

        new_data = pd.DataFrame(rows)
        for col in new_data.columns:
            intdf[col] = new_data[col]

        return True

    except Exception as e:
        print(f"  [INTERNAL]: Something went wrong: {e}")

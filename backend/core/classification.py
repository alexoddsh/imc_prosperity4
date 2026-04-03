import pandas as pd

#v1 (without identifiers)

def compute_classes(product: str, pdf: pd.DataFrame, tdf: pd.DataFrame) -> bool | None:
    mask = tdf["symbol"] == product.upper()

    if len(mask) == 0:
        raise ValueError(f"No trades found in TDF for {product}")
    
    trade_times = set(tdf.loc[mask, "timestamp"])
    price_times = set(pdf["timestamp"])
    missing = trade_times - price_times
    if missing: 
        raise KeyError(f"  [CLASSES]: TDF and PDF not complete or corrupt for {product}")
    
    try:
        pdf_indexed = pdf.set_index(["timestamp", "product"])

        for day, day_tdf in tdf[mask].groupby("day"):
            daily_low = day_tdf["price"].min() 
            daily_high = day_tdf["price"].max()
            
            for i in tdf.index[mask]:
                prev_index = None
                timestamp = tdf.iloc[i]["timestamp"]
                trade_price = tdf.iloc[i]["price"]
                volume = tdf.iloc[i]["quantity"]
                if pd.isna(volume) or pd.isna(trade_price):
                    raise ValueError(f"  [CLASSES]: Volume or price data missing from TDF for {product}")

                mid_price = pdf_indexed.at[(timestamp, product), "mid_price"].item()

                if trade_price >= mid_price:
                    if trade_price == 0.95 * daily_high and volume >= 10:
                        tdf.at[i,"buyer_class"], tdf.at[i,"seller_class"] = "INFORMED1", "MAKER2"
                    elif volume >= 10:
                        tdf.at[i,"buyer_class"], tdf.at[i, "seller_class"] = "TAKER2", "MAKER2"
                    else:
                        tdf.at[i, "buyer_class"], tdf.at[i, "seller_class"] = "TAKER1", "MAKER1"
                
                elif trade_price < mid_price:
                    if trade_price == 0.95 * daily_low and volume >= 10:
                        tdf.at[i, "buyer_class"], tdf.at[i, "seller_class"] = "MAKER2", "INFORMED1"
                    if volume >= 10:
                        tdf.at[i, "buyer_class"], tdf.at[i, "seller_class"] = "MAKER2", "TAKER2"
                    else:
                        tdf.at[i, "buyer_class"], tdf.at[i, "seller_class"] = "MAKER1", "TAKER1"
            
                #logic: simplified version looking for ultra informed traders that first bought at or near day low and then 
                #sold at or near day high. Since the 1st rounds are missing identifiers we will go off volume since large volumes 
                #are very rare in early rounds. Not guarantee but at least good probability of being the same trader
                if tdf.iloc[i]["quantity"] in tdf[tdf["buyer_class"] == "INFORMED1"]["quantity"].to_list() and tdf.iloc[i]["price"] >= mid_price:    
                    k = 0
                    for k in range(1, len(tdf)):
                        if tdf.iloc[i]["quantity"] == tdf.iloc[k]["quantity"] and tdf["buyer_class"] == "INFORMED1":
                            prev_index = k
                        else:
                            k += 1 
                    tdf.at[i, "seller_class"], tdf.at[prev_index, "buyer_class"] = "TOXIC", "TOXIC"
                
                elif tdf.iloc[i]["quantity"] in tdf[tdf["seller_class"] == "INFORMED1"]["quantity"].to_list() and tdf.iloc[i]["price"] < mid_price:
                    k = 0
                    for k in range(1, len(tdf)):
                        if tdf.iloc[i]["volume"] == tdf.iloc[k]["volume"] and tdf["seller_class"] == "INFORMED1":
                            prev_index = k
                        else:
                            k += 1 
                    tdf.at[i, "buyer_class"], tdf.at[prev_index, "seller_class"] = "TOXIC", "TOXIC"

                ##overwrite any previous classification if agent was ourselves
                if tdf.at[i, "seller"] == "SUBMISSION":
                    tdf.at[i, "seller_class"] = "ALGO"
                elif tdf.at[i, "buyer"] == "SUBMISSION":
                    tdf.at[i, "buyer_class"] = "ALGO"
                
                if prev_index is not None:
                    if tdf.at[prev_index, "seller"] == "SUBMISSION":
                        tdf.at[i, "seller_class"] = "ALGO"
                    elif tdf.at[prev_index, "buyer"] == "SUBMISSION":
                        tdf.at[prev_index, "buyer_class"] = "ALGO"
                
            return True
        
    except Exception as e:
        print(f"  [CLASSES]: An error occured {e}")
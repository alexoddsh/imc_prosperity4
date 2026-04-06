import pandas as pd

def compute_wallmid1(product: str, pdf: pd.DataFrame) -> bool:
    mask = pdf["product"] == product.upper()

    if not mask.any():
        raise ValueError(f" [WALLMID1]: No trades found in PDF for {product}")

    try:
        for i in pdf.index[mask]:
            vwaps = {}
            for t in ["bid", "ask"]:
                vsum = 0.0
                vol = 0.0

                for k in range(1, 4):
                    if pd.isna(pdf.at[i, f"{t}_price_{k}"] * pdf.at[i, f"{t}_volume_{k}"]):
                        break
                    
                    vsum += pdf.at[i, f"{t}_price_{k}"] * pdf.at[i, f"{t}_volume_{k}"]
                    vol += pdf.at[i, f"{t}_volume_{k}"]
                    
                if vsum !=0 and vol !=0:
                    vwaps[f"vwap_{t}"] = vsum / vol 
                else:
                    raise ValueError(f"  [WALLMID1]: Wallmid could not be computed for{product}")
        
            pdf.at[i, "wallmid1"] = round(((vwaps["vwap_ask"] + vwaps["vwap_bid"]) / 2), 2) 
            
        return True
        
    except Exception as e:
        print(f"  [WALLMID1]: An error occured: {e}")    

def compute_wallmid2(product: str, pdf: pd.DataFrame) -> bool:
    mask = pdf["product"] == product.upper()

    if not mask.any():
        raise ValueError(f"  [WALLMID2]: No trades found in PDF for {product}")

    try:
        for i in pdf.index[mask]:
            bid_vols = []
            ask_vols = []
            
            #note that .index returning only one value if there are multiple levels 
            #with the same liquidity actually isnt a problem because if there are multiple lvls 
            #we want the level with the lowest price to signal WALL lvl 
            for k in range(1, 4):
                bid_vols.append(pdf.at[i, f"bid_volume_{k}"])
                ask_vols.append(pdf.at[i, f"ask_volume_{k}"])
            
            bid_lvl_qty = max(bid_vols)
            ask_lvl_qty = max(ask_vols)

            bid_lvl_idx = bid_vols.index(bid_lvl_qty)
            ask_lvl_idx = ask_vols.index(ask_lvl_qty)

            bid_lvl_price = pdf.at[i, f"bid_price_{bid_lvl_idx+1}"]
            ask_lvl_price = pdf.at[i, f"ask_price_{ask_lvl_idx+1}"]
            
            pdf.at[i, "wallmid2"] = round(((ask_lvl_price + bid_lvl_price) / 2), 2)
        
        return True
    
    except Exception as e:
        print(f"  [WALLMID2]: An error occured: {e}")

def compute_wallmid3(product: str, pdf: pd.DataFrame) -> bool:
    mask = pdf["product"] == product.upper()
    
    if not mask.any():
        raise ValueError(f"  [WALLMID3]: No trades found in PDF for {product}")

    try:
        for i in pdf.index[mask]:
            bid_prices = []
            ask_prices = []
            
            for k in range(1, 4):
                bid_prices.append(pdf.at[i, f"bid_price_{k}"])
                ask_prices.append(pdf.at[i, f"ask_price_{k}"])

            buy_wall = min(bid_prices)
            sell_wall = max(ask_prices)

            pdf.at[i, "wallmid3"] = round((sell_wall + buy_wall) / 2, 2)
        
        return True

    except Exception as e:
        print(f"  [WALLMID3]: An error occured: {e}")


#v3
def compute_wallmid_ma(product: str, pdf: pd.DataFrame) -> bool:
    mask = pdf["product"] == product.upper()
    
    if not mask.any():
        raise ValueError(f"  [WALLMIDSMA]: No trades found in PDF for {product}")    
    try:
        pdf.loc[mask, "wallmidsma"] = pdf.loc[mask, "wallmid2"].rolling(window=10).mean()
        return True
    except Exception as e:
        print(f"  [WALLMIDMA]: An error occured: {e}")


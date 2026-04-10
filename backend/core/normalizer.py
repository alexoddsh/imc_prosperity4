import pandas as pd
import numpy as np

def compute_wallmid1(product: str, pdf: pd.DataFrame) -> bool:
    mask = pdf["product"] == product.upper()

    if not mask.any():
        raise ValueError(f" [WALLMID1]: No trades found in PDF for {product}")

    try:
        df = pdf.loc[mask]
        vwaps = {}
        for t in ["bid", "ask"]:
            prices = np.stack([df[f"{t}_price_{k}"].to_numpy() for k in range(1, 4)], axis=1)
            vols = np.stack([df[f"{t}_volume_{k}"].to_numpy() for k in range(1, 4)], axis=1)

            price_vol = prices * vols 
            sums = np.nansum(price_vol, axis=1)
            volumes = np.nansum(vols, axis=1)
            vwaps[t] = sums / volumes 
            
        vwap = np.round((vwaps["ask"] + vwaps["bid"]) / 2, 2)
        pdf.loc[mask, "wallmid1"] = pd.Series(vwap, index=df.index)

        return True

    except Exception as e:
        print(f"  [WALLMID1]: An error occured: {e}")    

def compute_wallmid2(product: str, pdf: pd.DataFrame) -> bool:
    mask = pdf["product"] == product.upper()

    if not mask.any():
        raise ValueError(f"  [WALLMID2]: No trades found in PDF for {product}")

    try:
        df = pdf.loc[mask]
        max_prices = {}
        for t in ["bid", "ask"]:
            prices = np.stack([df[f"{t}_price_{k}"].to_numpy() for k in range(1, 4)], axis=1)
            vols = np.stack([df[f"{t}_volume_{k}"].to_numpy() for k in range(1, 4)], axis=1)
            
            volmax_idx = np.nanargmax(vols, axis=1) 
            volmax_prices = prices[np.arange(len(volmax_idx)), volmax_idx]
            max_prices[t] = volmax_prices
            
        wallmid = np.round((max_prices["ask"] + max_prices["bid"]) / 2, 2) 
        pdf.loc[mask, "wallmid2"] = pd.Series(wallmid, index=df.index)

        return True
    
    except Exception as e:
        print(f"  [WALLMID2]: An error occured: {e}")

def compute_wallmid3(product: str, pdf: pd.DataFrame) -> bool:
    mask = pdf["product"] == product.upper()
    
    if not mask.any():
        raise ValueError(f"  [WALLMID3]: No trades found in PDF for {product}")

    try:
        df = pdf.loc[mask]
        ob_prices = {}
        for t in ["bid", "ask"]:
            prices = np.stack([df[f"{t}_price_{k}"].to_numpy() for k in range(1, 4)], axis=1) 
            if t == "bid":
                low_bid = np.nanmin(prices, axis=1) #collapse cols to get on element per row
                ob_prices[t] = low_bid
            elif t == "ask":
                max_ask = np.nanmax(prices, axis=1)
                ob_prices[t] = max_ask

        wallmid = np.round((ob_prices["ask"] + ob_prices["bid"]) / 2, 2)
        pdf.loc[mask, "wallmid3"] = pd.Series(wallmid, index=df.index)
        
        return True

    except Exception as e:
        print(f"  [WALLMID3]: An error occured: {e}")


def compute_wallmid_corrected(product: str, pdf: pd.DataFrame) -> bool:
    mask = pdf["product"] == product.upper()

    if not mask.any():
        raise ValueError(f"  [WALLMID_CORR]: No trades found in PDF for {product}")

    try:
        df = pdf.loc[mask]

        bid_prices = np.stack([df[f"bid_price_{k}"].to_numpy() for k in range(1, 4)], axis=1)
        ask_prices = np.stack([df[f"ask_price_{k}"].to_numpy() for k in range(1, 4)], axis=1)

        min_bid = np.nanmin(bid_prices, axis=1)
        max_ask = np.nanmax(ask_prices, axis=1)
        wallmid3 = (max_ask + min_bid) / 2

        bbo_mid = (df["bid_price_1"].to_numpy() + df["ask_price_1"].to_numpy()) / 2
        bbo_offset = bbo_mid - wallmid3
        core_mask = np.abs(bbo_offset) <= 0.5
        correction = np.where(core_mask, 0.734 * bbo_offset, 0.0)

        corrected = np.round(wallmid3 + correction, 6)
        pdf.loc[mask, "wallmido"] = pd.Series(corrected, index=df.index)

        return True

    except Exception as e:
        print(f"  [WALLMID_CORR]: An error occured: {e}")


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


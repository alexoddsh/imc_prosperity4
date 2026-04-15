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
            out = np.full(sums.shape, np.nan, dtype=float)
            vwaps[t] = np.divide(sums, volumes, out=out, where=volumes != 0)
            
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
            
            all_nan = np.all(np.isnan(vols), axis=1)
            safe_vols = np.where(np.isnan(vols), -np.inf, vols)
            volmax_idx = np.argmax(safe_vols, axis=1)
            volmax_prices = prices[np.arange(len(volmax_idx)), volmax_idx].astype(float)
            volmax_prices[all_nan] = np.nan
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
            all_nan = np.all(np.isnan(prices), axis=1)
            if t == "bid":
                safe = np.where(np.isnan(prices), np.inf, prices)
                out = np.min(safe, axis=1)
            else:
                safe = np.where(np.isnan(prices), -np.inf, prices)
                out = np.max(safe, axis=1)
            out = out.astype(float)
            out[all_nan] = np.nan
            ob_prices[t] = out

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

        bid_all_nan = np.all(np.isnan(bid_prices), axis=1)
        ask_all_nan = np.all(np.isnan(ask_prices), axis=1)
        min_bid = np.min(np.where(np.isnan(bid_prices), np.inf, bid_prices), axis=1).astype(float)
        max_ask = np.max(np.where(np.isnan(ask_prices), -np.inf, ask_prices), axis=1).astype(float)
        min_bid[bid_all_nan] = np.nan
        max_ask[ask_all_nan] = np.nan
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
        pdf.loc[mask, "wallmidsma"] = pdf.loc[mask, "wallmid3"].rolling(window=5).mean()
        return True
    except Exception as e:
        print(f"  [WALLMIDMA]: An error occured: {e}")


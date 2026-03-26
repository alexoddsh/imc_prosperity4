import pandas as pd
import numpy as np

def compute_all_indicators(pdf: pd.DataFrame) -> pd.DataFrame:
    pdf = pdf.copy()
    
    # --- WallMid1 ---
    tpv, tv = np.zeros(len(pdf)), np.zeros(len(pdf))
    for i in range(1, 4):
        for pcol, vcol in [(f"bid_price_{i}", f"bid_volume_{i}"), (f"ask_price_{i}", f"ask_volume_{i}")]:
            if pcol in pdf.columns and vcol in pdf.columns:
                p = pdf[pcol].values.astype(float)
                v = np.abs(pdf[vcol].values.astype(float))
                valid = np.isfinite(p) & np.isfinite(v)
                tpv += np.where(valid, p * v, 0)
                tv += np.where(valid, v, 0)
    pdf["wallmid1"] = np.where(tv > 0, tpv / tv, np.nan)

    # --- WallMid2 ---
    best_bid_p, best_bid_v = np.full(len(pdf), np.nan), np.zeros(len(pdf))
    best_ask_p, best_ask_v = np.full(len(pdf), np.nan), np.zeros(len(pdf))
    for i in range(1, 4):
        bp, bv = f"bid_price_{i}", f"bid_volume_{i}"
        ap, av = f"ask_price_{i}", f"ask_volume_{i}"
        if bp in pdf.columns:
            mask = (np.abs(pdf[bv]) > best_bid_v)
            best_bid_p = np.where(mask, pdf[bp], best_bid_p)
            best_bid_v = np.where(mask, np.abs(pdf[bv]), best_bid_v)
        if ap in pdf.columns:
            mask = (np.abs(pdf[av]) > best_ask_v)
            best_ask_p = np.where(mask, pdf[ap], best_ask_p)
            best_ask_v = np.where(mask, np.abs(pdf[av]), best_ask_v)
    pdf["wallmid2"] = (best_bid_p + best_ask_p) / 2

    return pdf
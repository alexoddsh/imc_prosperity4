from email.policy import default
import pandas as pd
import numpy as np

#v1 (without identifiers)

def compute_classes(product: str, pdf: pd.DataFrame, tdf: pd.DataFrame) -> bool | None:
    mask = tdf["symbol"] == product.upper()

    if not mask.any():
        raise ValueError(f"No trades found in TDF for {product}")
    
    try:
        for day, day_tdf in tdf[mask].groupby("day"):
            #step 1 compute base classes
            daily_max = day_tdf["price"].max()
            daily_low = day_tdf["price"].min()
            
            original_index = day_tdf.index
            day_tdf = day_tdf.merge(pdf[["timestamp", "product", "mid_price"]], left_on=["timestamp", "symbol"], right_on=["timestamp", "product"], how="left")
            day_tdf.index = original_index
            above_mid = day_tdf["price"] >= day_tdf["mid_price"]
            below_mid = day_tdf["price"] < day_tdf["mid_price"]

            near_high = abs(day_tdf["price"] - daily_max) / daily_max < 0.01 
            near_low = abs(day_tdf["price"] - daily_low) / daily_low < 0.01
            large_vol = day_tdf["quantity"] >= 10
            algo_buy = day_tdf["buyer"] == "SUBMISSION"
            algo_sell = day_tdf["seller"] == "SUBMISSION" 

            conditions_buyer = [
                algo_buy, #algo
                above_mid & near_low & large_vol, #informed
                above_mid & large_vol, #big taker
                above_mid, #small taker
                below_mid & large_vol, #big maker
                below_mid #normal maker
            ]

            conditions_seller = [
                algo_sell, #algo
                below_mid & near_high & large_vol, #informed
                below_mid & large_vol, #big taker
                below_mid, #small taker
                above_mid & large_vol, #big maker
                above_mid #small maker
            ]

            choices = ["ALGO", "INFORMED1", "TAKER2", "TAKER1", "MAKER2", "MAKER1"]
            day_tdf["buyer_class"] = np.select(conditions_buyer, choices, default="UNKNOWN")
            day_tdf["seller_class"] = np.select(conditions_seller, choices, default="UNKNOWN")
            
            #step 2 with base classes check for TOXIC
            ibuyers = day_tdf[day_tdf["buyer_class"] == "INFORMED1"]["quantity"]
            isellers = day_tdf[day_tdf["seller_class"] == "INFORMED1"]["quantity"]
            
            for bidx in ibuyers.index:
                matched = isellers[isellers == ibuyers[bidx]].index
                if len(matched) > 0:
                    sidx = matched[0]
                    day_tdf.at[sidx, "seller_class"] = day_tdf.at[bidx, "buyer_class"] = "TOXIC"
            
            tdf.loc[day_tdf.index, "buyer_class"] = day_tdf["buyer_class"]
            tdf.loc[day_tdf.index, "seller_class"] = day_tdf["seller_class"]
            
        return True
        
    except Exception as e:
        print(f"  [CLASSIFICATION]: An error occured {e}")
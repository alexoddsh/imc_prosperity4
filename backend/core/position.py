import pandas as pd

##note simple file for now but we could use to calculate more complex position logic later
#for now just computes going position but maybe could implement more complex "skew" testing for backtest to for
#example see how would position have changed if we did X Y Z

def compute_position(product: str, tdf: pd.DataFrame) -> bool:
    mask = tdf["symbol"] == product.upper()

    if not mask.any():
        raise ValueError(f"--[POSITION]--: No data in PDF for {product}")

    tdf.loc[mask, "algo_position"] = 0

    try:
        for day, day_tdf in tdf[mask].groupby("day"):
            k = 0

            for i in day_tdf.index:
                if k == 0:
                    prev = 0
                else:
                    prev = tdf.at[day_tdf.index[k-1], "algo_position"]

                if "SUBMISSION" not in [tdf.at[i, "buyer"], tdf.at[i, "seller"]]:
                    tdf.at[i, "algo_position"] = prev
                elif tdf.at[i, "buyer"] == "SUBMISSION":
                    tdf.at[i, "algo_position"] = prev + tdf.at[i, "quantity"]
                elif tdf.at[i, "seller"] == "SUBMISSION":
                    tdf.at[i, "algo_position"] = prev - tdf.at[i, "quantity"]

                k += 1
                        
        return True

    except Exception as e:
        print(f"--[POSITION]-- An error occured: {e}")

            


    

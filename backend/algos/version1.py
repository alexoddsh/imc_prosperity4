from datamodel import TradingState
import pandas as pd
import jsonpickle

#PRODUCT TYPE MAPPING
EMERALDS = "PURE_MARKET"
TOMATOES = "DRIFT_MARKET"

#TRUE PRICE
EMERALDS = 10000

class Trader:
    def run(self, state: TradingState):
        if state.traderData:
            memory = jsonpickle.decode(state.traderData)
        else:
            algo_trades = pd.DataFrame({
                    "timestamp": [0], 
                    "symbol": ["EMERALDS", "TOMATOES"], 
                    "price": [0], 
                    "quantity": [0]
                })
            
            algo_trades = algo_trades.astype({
                "timestamp": "uint16", 
                "symbol": "category", ##saves a TON of space
                "price": "uint16", #price cannot be negative
                "quantity": "int16"
            })

            memory = algo_trades
        
        conversions = 1
        traderData = jsonpickle.encode(memory)
        return result, conversions, traderData
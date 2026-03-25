from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string


class Trader:

    def run(self, state: TradingState):
        
        print("traderData: " + state.traderData)
        print(str(state.observations.conversionObservations.get("TOMATOES")))
        print(str(state.observations.plainValueObservations.get("TOMATOES")))

        result = {}

        best_bid = max(state.order_depths["TOMATOES"].buy_orders.keys())
        best_bid_qty = state.order_depths["TOMATOES"].buy_orders[best_bid]
        
        best_ask = min(state.order_depths["TOMATOES"].sell_orders.keys())
        best_ask_qty = state.order_depths["TOMATOES"].sell_orders[best_ask]
            
        traderData = ""  
        conversions = 0
        return result, conversions, traderData
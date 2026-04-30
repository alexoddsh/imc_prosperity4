from datamodel import TradingState, Order
from typing import List, Dict
import pandas as pd
import numpy as np

# --- GRID PARAMS ---
BEDY = 0
PRICKEN = 0
# --- END GRID PARAMS ---

class Trader:
    def run(self, state: TradingState):

        results = {}
        traderData = state.traderData
        conversions = 0

        ob_sounds = state.order_depths["GALAXY_SOUNDS_BLACK_HOLES"]
        ob_garlic = state.order_depths["OXYGEN_SHAKE_GARLIC"]

        sounds_bids = ob_sounds.buy_orders
        sounds_asks = ob_sounds.sell_orders
        garlic_bids = ob_garlic.buy_orders
        garlic_asks = ob_garlic.sell_orders

        garlic_wmid = round((min(garlic_bids.keys()) + max(garlic_asks.keys())) / 2, 2)
        sounds_wmid = round((min(sounds_bids.keys()) + max(sounds_asks.keys())) / 2, 2)

        spread = garlic_wmid - sounds_wmid
        curr_pos_sounds = state.position.get("GALAXY_SOUNDS_BLACK_HOLES", 0)
        curr_pos_garlic = state.position.get("OXYGEN_SHAKE_GARLIC", 0)

        max_buy_sounds = 10-curr_pos_sounds
        max_sell_sounds = -(10+curr_pos_sounds)
        max_buy_garlic = 10-curr_pos_garlic
        max_sell_garlic = -(10+curr_pos_sounds)        

        sounds_orders: List[Order] = []
        garlic_orders: List[Order] = []

        #200
        if abs(spread) > 200:
            #enters sounds
            if garlic_wmid > sounds_wmid:
                sounds_orders.append(Order("GALAXY_SOUNDS_BLACK_HOLES", min(sounds_asks.keys()), max_buy_sounds))
                garlic_orders.append(Order("OXYGEN_SHAKE_GARLIC", max(garlic_bids.keys()), max_sell_garlic))
            else:
                sounds_orders.append(Order("GALAXY_SOUNDS_BLACK_HOLES", max(sounds_bids.keys()), max_sell_sounds))
                garlic_orders.append(Order("OXYGEN_SHAKE_GARLIC", min(garlic_asks.keys()), max_buy_garlic))
        
        elif abs(spread) < 4 and (abs(curr_pos_sounds) > 0 and abs(curr_pos_garlic) > 0):
            if curr_pos_sounds > 0:
                sounds_orders.append(Order("GALAXY_SOUNDS_BLACK_HOLES", max(sounds_bids.keys()), -curr_pos_sounds))
            else:
                sounds_orders.append(Order("GALAXY_SOUNDS_BLACK_HOLES", min(sounds_asks.keys()), -curr_pos_sounds))
            if curr_pos_garlic > 0:
                garlic_orders.append(Order("OXYGEN_SHAKE_GARLIC", max(sounds_bids.keys()), -curr_pos_sounds))
            else:
                garlic_orders.append(Order("OXYGEN_SHAKE_GARLIC", min(sounds_asks.keys()), -curr_pos_sounds))


        results["GALAXY_SOUNDS_BLACK_HOLES"] = sounds_orders
        results["OXYGEN_SHAKE_GARLIC"] = garlic_orders

        return results, conversions, traderData
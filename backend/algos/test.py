from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import string

# --- GRID PARAMS ---
BEDY = 0
PRICKEN = 0
# --- END GRID PARAMS ---

class Trader:
    def run(self, state: TradingState):

        curr_pos = state.position.get("ASH_COATED_OSMIUM", 0)
        max_buy = 80-curr_pos
        max_sell = -(80+curr_pos)
        order_book = state.order_depths["ASH_COATED_OSMIUM"]

        bids: Dict = order_book.buy_orders
        asks: Dict = order_book.sell_orders

        best_bid_price = max(bids.keys())
        best_bid_qty = bids[best_bid_price]

        best_ask_price = min(asks.keys())
        best_ask_qty = asks[best_ask_price] 

        ask_wall = max(asks)
        bid_wall = min(bids)
        wall_mid = (ask_wall+bid_wall)/2
        
        results = {}
        orders: List[Order] = []

        if best_bid_price > wall_mid or best_ask_price < wall_mid:
            if best_bid_price > wall_mid:
                orders.append(Order("ASH_COATED_OSMIUM", best_bid_price, -best_bid_qty))
                max_sell += best_bid_qty
                ##find second best level
                bids.pop(best_bid_price)
                l2_best_bid_price = max(bids.keys())
                if l2_best_bid_price < wall_mid:
                    orders.append(Order("ASH_COATED_OSMIUM", l2_best_bid_price+1, max_buy))
                else:
                    print("L2 unexpectedly crossed wall_mid")
            elif best_ask_price < wall_mid:
                orders.append(Order("ASH_COATED_OSMIUM", best_ask_price, -best_ask_qty))
                max_buy -= best_ask_qty
                asks.pop(best_ask_price)
                l2_best_ask_price = min(asks.keys())
                if l2_best_ask_price > wall_mid:
                    orders.append(Order("ASH_COATED_OSMIUM", l2_best_ask_price-1, max_sell))
                else:
                    print("L2 unexpectedly crossed wall_mid")
        else:
            orders.append(Order("ASH_COATED_OSMIUM", best_bid_price+1, max_buy))
            orders.append(Order("ASH_COATED_OSMIUM", best_ask_price-1, max_sell))

        results["ASH_COATED_OSMIUM"] = orders
        traderData = ""
        conversions = 0
        
        return results, conversions, traderData
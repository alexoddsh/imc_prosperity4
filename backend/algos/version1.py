from datamodel import TradingState, Order, Logger
import jsonpickle

#PRODUCT TYPE MAPPING
EMERALDS = "PURE_MARKET"
TOMATOES = "DRIFT_MARKET"

#POSITION LIMITS
POSITION_LIMITS = {
    "EMERALDS": 80,
    "TOMATOES": 80
}

#TRUE PRICE
EMERALDS = 10000

class Trader:

    def __init__(self):
        self.logger = Logger()

    def run(self, state: TradingState):

        if state.traderData:
            memory = jsonpickle.decode(state.traderData)
        else:
            memory = []
        
        result = {}

        for product in state.order_depths:
            if product == "EMERALDS":
                orders = []

                best_bid_price, best_bid_vol = next(iter(state.order_depths["EMERALDS"].buy_orders.items()))
                best_ask_price, best_ask_vol = next(iter(state.order_depths["EMERALDS"].sell_orders.items()))
                
                current_pos = state.position.get("EMERALDS", 0)
                net_position_margin = POSITION_LIMITS["EMERALDS"] - current_pos

                #1. take any profitable existing trades
                if best_ask_price < 10000:
                    algo_buy_order_t1 = Order(product, best_ask_price, best_ask_vol)
                    orders.append(algo_buy_order_t1)
                    net_position_margin -= best_ask_vol
                if best_bid_price > 10000:
                    algo_sell_order_t1 = Order(product, best_bid_price, best_bid_vol)
                    orders.append(algo_sell_order_t1)
                    net_position_margin += best_bid_vol

                #2. make market just inside spread
                algo_bid_price = best_bid_price + 1 #just inside the spread :)
                algo_bid_vol = int((net_position_margin - 1) / 2) #ensures rounding never goes in the wrong dir

                algo_ask_price = best_ask_price - 1  
                algo_ask_vol = -int((net_position_margin - 1) / 2)

                algo_buy_order_m1 = Order(product, algo_bid_price, algo_bid_vol)
                if algo_buy_order_m1:
                    orders.append(algo_buy_order_m1) 

                algo_sell_order_m1 = Order(product, algo_ask_price, algo_ask_vol)
                if algo_sell_order_m1:
                    orders.append(algo_sell_order_m1)

                result[product] = orders
            
        conversions = 0
        traderData = jsonpickle.encode(memory)

        self.logger.flush(state, result, conversions, traderData)

        return result, conversions, traderData
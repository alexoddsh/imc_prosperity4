from datamodel import TradingState, Order, Logger
import json

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
            memory = json.loads(state.traderData)
        else:
            memory = {}

        #results is in format {product1: [Order1, Order2], product2: [Order1, Order2]}
        result = {}

        for product in state.order_depths:
            if product == "EMERALDS":
                orders_emeralds = []

                best_bid_price, best_bid_vol = next(iter(state.order_depths["EMERALDS"].buy_orders.items()))
                best_ask_price, best_ask_vol = next(iter(state.order_depths["EMERALDS"].sell_orders.items()))
                
                current_pos = state.position.get("EMERALDS", 0)
                net_position_margin = POSITION_LIMITS["EMERALDS"] - current_pos

                #1. take any profitable existing trades
                if best_ask_price < 10000:
                    algo_buy_order_t1 = Order(product, best_ask_price, best_ask_vol)
                    orders_emeralds.append(algo_buy_order_t1)
                    net_position_margin -= best_ask_vol
                if best_bid_price > 10000:
                    algo_sell_order_t1 = Order(product, best_bid_price, best_bid_vol)
                    orders_emeralds.append(algo_sell_order_t1)
                    net_position_margin += best_bid_vol

                #2. make market just inside spread
                algo_bid_price = best_bid_price + 1 #just inside the spread :)
                algo_bid_vol = int((net_position_margin - 1) / 2) #ensures rounding never goes in the wrong dir

                algo_ask_price = best_ask_price - 1  
                algo_ask_vol = -int((net_position_margin - 1) / 2)

                algo_buy_order_m1 = Order(product, algo_bid_price, algo_bid_vol)
                if algo_buy_order_m1:
                    orders_emeralds.append(algo_buy_order_m1) 

                algo_sell_order_m1 = Order(product, algo_ask_price, algo_ask_vol)
                if algo_sell_order_m1:
                    orders_emeralds.append(algo_sell_order_m1)

                result[product] = orders_emeralds
            
            if product == "TOMATOES":
                orders_tomatoes = []
                continue
        
        #critical here, we do not want to store the complex heavy class objects 
        #that results consists of. ALSO we do not need to save the symbol in the keys and order objs
        #but lets be lazy fow now 
        if len(orders_emeralds) != 0:
            emeralds_data = [[o.price, o.quantity] for o in orders_emeralds]
        if len(orders_tomatoes) != 0:
            tomatoes_data = [[o.price, o.quantity] for o in orders_tomatoes]
        
        memory[str(state.timestamp)] = [emeralds_data, tomatoes_data] 
        
        conversions = 0
        traderData = json.dumps(memory, separators=(',', ':'))

        self.logger.flush(state, result, conversions, traderData)
 
        return result, conversions, traderData
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
                
                speculative_position = state.position.get("EMERALDS", 0) ##gets the actual current pos
                
                #1. take any profitable existing trades
                if best_ask_price < 10000:
                    speculative_position += best_ask_vol
                    
                if best_bid_price > 10000:
                    speculative_position -= best_bid_vol
                
                net_position_margin = POSITION_LIMITS["EMERALDS"] - abs(speculative_position)
                if net_position_margin >= 0: 
                    algo_buy_order_t1 = Order(product, best_ask_price, best_ask_vol)
                    algo_sell_order_t1 = Order(product, best_bid_price, best_bid_vol)
                    orders_emeralds.append(algo_buy_order_t1)
                    orders_emeralds.append(algo_sell_order_t1)

                #2. make market just inside spread
                skew_rate = (speculative_position/POSITION_LIMITS["EMERALDS"]) #imagine long 40/80 = 0.5 means we need to rebalance
                
                algo_bid_price = best_bid_price + 1 #just inside the spread :)
                algo_bid_vol = int((net_position_margin * (1-skew_rate) / 2))

                algo_ask_price = best_ask_price - 1  
                algo_ask_vol = -int((net_position_margin * (1+skew_rate) / 2))

                if algo_bid_vol > 0:
                    algo_buy_order_m1 = Order(product, algo_bid_price, algo_bid_vol)
                    orders_emeralds.append(algo_buy_order_m1) 
                    
                if algo_ask_vol < 0:
                    algo_sell_order_m1 = Order(product, algo_ask_price, algo_ask_vol)
                    orders_emeralds.append(algo_sell_order_m1)

                result[product] = orders_emeralds
            
            if product == "TOMATOES":
                orders_tomatoes = []
                continue
        
        
        conversions = 0

        #internal data stream (use print in prod)
        emeralds_data = [[o.symbol, o.price, o.quantity] for o in orders_emeralds]
        tomatoes_data = [[o.symbol, o.price, o.quantity] for o in orders_tomatoes]
        self.logger.print(f"[DATA] {json.dumps({str(state.timestamp): [emeralds_data, tomatoes_data]})}")
        
        #trader data for algo
        traderData = json.dumps(memory, separators=(',', ':'))
        
        self.logger.flush(state, result, conversions, traderData)
 
        return result, conversions, traderData
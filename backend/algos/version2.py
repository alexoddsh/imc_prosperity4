from datamodel import TradingState, Order
import json

#POSITION LIMITS
POSITION_LIMITS = {
    "EMERALDS": 80,
    "TOMATOES": 80
}

class Logger:
    def __init__(self) -> None:
        self.logs = ""

    def print(self, *objects: any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state, orders, conversions, traderData):
        print(json.dumps({
            "sandboxLog": self.logs,
            "lambdaLog": traderData,
            "timestamp": state.timestamp,
        }, separators=(",", ":")))
        self.logs = ""


class MarketTrader:
    def __init__(self, product, state):
        self.product = product #what product this instance trades
        self.state = state 
        
        self.position_limit = POSITION_LIMITS.get(self.product.upper(), 0)
        self.current_position = self.state.position.get(self.product.upper(), 0) 

        self.best_bid_price, self.best_bid_volume = self.get_best_bid()
        self.best_ask_price, self.best_ask_volume = self.get_best_ask()
        self.buy_orders, self.sell_orders = self.get_order_depths()

        self.wall_mid1, self.wall_mid2 = self.compute_wallmid1(), self.compute_wallmid1()

    def bid(self, bp, bv, orders):
        orders.append(Order(self.product, bp, int(bv)))

    def ask(self, sp, sv, orders):
        orders.append(Order(self.product, sp, int(-sv)))
            
    def get_best_bid(self):
        bbp, bbv = next(iter(self.state.order_depths[self.product].buy_orders.items()))
        return bbp, bbv
    
    def get_best_ask(self):
        bap, bav = next(iter(self.state.order_depths[self.product].sell_orders.items()))
        return bap, bav
    
    def get_order_depths(self):
        for i in self.state.order_depths: 
            if i == self.product:
                product_depth = self.state.order_depths[self.product]
                buy_orders = product_depth.buy_orders
                sell_orders = product_depth.sell_orders
        return buy_orders, sell_orders

    def compute_wallmid1(self):
        vwaps = []
        for side in ["sell", "buy"]:
            attr = f"{side}_orders"
            sum, vol = 0, 0
            orders = getattr(self, attr)
            for prc, qty in orders.items():
                sum += prc*qty
                vol += qty
                vwaps.append(round((sum / vol), 2))
        wallmid = round((vwaps[0] + vwaps[1]) / 2, 2)
        return wallmid
    
    def compute_wallmid2(self):
        swqty = max(self.sell_orders.values())
        swpr = 0
        for key, val in self.sell_orders.items():
            if val == swqty:
                swpr = key
        
        bwqty = max(self.buy_orders.values())
        bwpr = 0
        for key, val in self.buy_orders.items():
            if val == bwqty:
                bwpr = key
        
        wallmid = round(((swpr + bwpr) / 2), 2)
        return wallmid


class BasicMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self):
        orders = []
        if self.wall_mid2 is not None:

            ##TAKING ALL PROFITABLE
            for sp, sv in self.sell_orders.items():
                if sp < self.wall_mid2:
                    self.bid(sp, sv, orders)
            
            for bp, bv in self.buy_orders.items():
                if bp > self.wall_mid2:
                    self.ask(bp, bv, orders)
            
            ##MAKING MARKET
            skew_rate = self.current_position / self.position_limit
            if self.best_ask_price - 1 > self.wall_mid2:
                vol_order = (self.position_limit - abs(self.current_position) / 2) * (1+skew_rate)
                self.ask(self.best_ask_price-1, vol_order, orders)
            
            if self.best_bid_price + 1 < self.wall_mid2:
                vol_order = (self.position_limit - abs(self.current_position) / 2) * (1-skew_rate)
                self.bid(self.best_bid_price+1, vol_order, orders)
                
        return {self.product: orders}
           
class Trader:
    def __init__(self):
        self.logger = Logger()

    def run(self, state: TradingState):
        result = {}
        logs = []

        traders = {
            "TOMATOES": BasicMaker,
            "EMERALDS": BasicMaker
        }
        for product, trader in traders.items():
            trader_instance = trader(product, state)

            orders = trader_instance.produce_orders()
            product_orders = orders[product]
            logs.append([[o.symbol, o.price, o.quantity] for o in product_orders]) #for internal visualization tool of missed orders
            result.update(orders)
            
        conversions = 0
        traderData = ""

        self.logger.print(f"[DATA] {json.dumps({str(state.timestamp): logs})}")
        self.logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData
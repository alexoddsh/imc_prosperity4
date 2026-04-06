import json
from datamodel import TradingState, Order

#POSITION LIMITS
POSITION_LIMITS = {
    "EMERALDS": 80,
    "TOMATOES": 80
}

#TECHNICALS
MA_WINDOW = 10
MAX_HISTORY = 200

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
    def __init__(self, product, state, logger):
        self.product = product #what product this instance trades
        self.state = state 
        self.logger = logger
        self.trader_data = self.get_trader_data()
        
        self.position_limit = POSITION_LIMITS.get(self.product.upper(), 0)
        self.current_position = self.state.position.get(self.product.upper(), 0) 

        self.best_bid_price, self.best_bid_volume = self.get_best_bid()
        self.best_ask_price, self.best_ask_volume = self.get_best_ask()
        self.buy_orders, self.sell_orders = self.get_order_depths()

        self.wall_mid1, self.wall_mid2, self.wall_midma = self.compute_wallmid1(), self.compute_wallmid2(), self.compute_wallmidma()

    def get_trader_data(self):
        trader_data = {}
        try:
            if self.state.traderData and self.state.traderData != "":
                trader_data = json.loads(self.state.traderData)
            else:
                trader_data = {}
        except Exception:
            print("Trader data exploded")
        
        if len(trader_data) > MAX_HISTORY:
            for old_key in list(trader_data.keys())[:-MAX_HISTORY]:
                del trader_data[old_key]
        return trader_data

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
        depth = self.state.order_depths[self.product]
        return depth.buy_orders, depth.sell_orders

    def compute_wallmid1(self):
        vwaps = []
        for side in ["sell", "buy"]:
            attr = f"{side}_orders"
            asum, vol = 0, 0
            orders = getattr(self, attr)
            for prc, qty in orders.items():
                asum += prc*abs(qty)
                vol += abs(qty)
            vwaps.append(round((asum / vol), 2))
        wallmid = round((vwaps[0] + vwaps[1]) / 2, 2)
        return wallmid
    
    def compute_wallmid2(self):
        b_vols = list(self.buy_orders.values())
        s_vols = list(self.sell_orders.values())
        
        b_max = max(b_vols)
        s_max = min(s_vols)  
        
        b_prc = list(self.buy_orders.keys())[b_vols.index(b_max)]
        s_prc = list(self.sell_orders.keys())[s_vols.index(s_max)]
        
        wallmid = round((b_prc + s_prc) / 2, 2)
        self.trader_data[f"{self.state.timestamp}_{self.product}"] = wallmid
        
        return wallmid
    
    def compute_wallmidma(self):
        window_data = []
        reversed_items = list(self.trader_data.items())[::-1]
        if len(self.trader_data) >= MA_WINDOW:
            for k, v in reversed_items:
                if str(self.product) in k:
                    window_data.append(v)
                    if len(window_data) == MA_WINDOW:
                        break
        
        if len(window_data) == MA_WINDOW:
            sme = round(sum(window_data) / len(window_data), 2)
            return sme
        
class BasicMaker(MarketTrader):
    def __init__(self, product, state, logger):
        super().__init__(product, state, logger)

    def produce_orders(self):
        orders = []
        if self.wall_midma is not None:
            
            ##TAKING ALL PROFITABLE
            for sp, sv in self.sell_orders.items():
                if int(sp) < self.wall_midma:
                    self.bid(sp, sv, orders)
            
            for bp, bv in self.buy_orders.items():
                if int(bp) > self.wall_midma:
                    self.ask(bp, bv, orders)
            
            ##MAKING MARKET
            skew_rate = self.current_position / self.position_limit
            if int(self.best_ask_price - 1) > self.wall_midma:
                vol_order = (self.position_limit - abs(self.current_position) / 2) * (1+skew_rate)
                self.ask(self.best_ask_price-1, vol_order, orders)
            
            if int(self.best_bid_price + 1) < self.wall_midma:
                vol_order = (self.position_limit - abs(self.current_position) / 2) * (1-skew_rate)
                self.bid(self.best_bid_price+1, vol_order, orders)
                
        return {self.product: orders}
           
class Trader:
    def __init__(self):
        self.logger = Logger()
    
    def run(self, state: TradingState):
        result = {}
        outgoing = {}
        logs = []

        traders = {
            "TOMATOES": BasicMaker,
            "EMERALDS": BasicMaker
        }
        for product, TraderClass in traders.items():
            trader_instance = TraderClass(product, state, self.logger)
            outgoing.update(trader_instance.trader_data)

            orders = trader_instance.produce_orders()        
            product_orders = orders[product]
            logs.append([[o.symbol, o.price, o.quantity] for o in product_orders]) #for internal visualization tool of missed orders
            result.update(orders)
            
        conversions = 0

        traderData = json.dumps(outgoing)
        self.logger.print(f"[DATA] {json.dumps({str(state.timestamp): logs})}")
        self.logger.flush(state, result, conversions, traderData)

        return result, conversions, traderData
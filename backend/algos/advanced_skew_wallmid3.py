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

        self.wall_mid1, self.wall_mid2, self.wall_mid3, self.wall_midma = self.compute_wallmid1(), self.compute_wallmid2(), self.compute_wallmid3(), self.compute_wallmidma()

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

    #note, here we protect against zero orders 
    def bid(self, bp, bv, orders):
        if int(bv) == 0: 
            return
        orders.append(Order(self.product, bp, int(abs(bv))))

    def ask(self, sp, sv, orders):
        if int(sv) == 0: 
            return
        orders.append(Order(self.product, sp, int(-abs(sv))))
            
    def get_best_bid(self):
        bbp, bbv = next(iter(self.state.order_depths[self.product].buy_orders.items()))
        return bbp, bbv
    
    def get_best_ask(self):
        bap, bav = next(iter(self.state.order_depths[self.product].sell_orders.items()))
        return bap, bav #note BAV is negative
    
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
                asum += prc*abs(qty) #sell quantities are negative
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
    
    def compute_wallmid3(self):
        buy_wall = min(prc for prc, _ in self.buy_orders.items())
        sell_wall = max(prc for prc, _ in self.sell_orders.items())
        wallmid = round((sell_wall + buy_wall) / 2, 2)
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
            indicator = self.wall_midma
        else:
            indicator = self.wall_mid3

        #EMERALS = constant true price no just max bid no inventory risk, therefore just maximize
        #orders without hitting limit
        if self.product == "EMERALDS":
            
            ##TAKING ALL PROFITABLE
            allowed_long = POSITION_LIMITS.get(self.product) - self.current_position
            allowed_short = POSITION_LIMITS.get(self.product) + self.current_position

            for sp, sv in self.sell_orders.items():
                if int(sp) < indicator and allowed_long > 0: 
                    bid_vol = min(abs(sv), allowed_long)
                    allowed_long -= bid_vol
                    self.bid(sp, bid_vol, orders)
            
            for bp, bv in self.buy_orders.items():
                if int(bp) > indicator and allowed_short > 0:
                    ask_vol = min(bv, allowed_short)
                    allowed_short -= ask_vol
                    self.ask(bp, ask_vol, orders)
            
            ##MAKING MARKET
            if int(self.best_bid_price + 1) < indicator and allowed_long > 0:
                bid_vol = min(allowed_long, 15)
                self.bid(self.best_bid_price+1, bid_vol, orders)

            if int(self.best_ask_price - 1) > indicator and allowed_short > 0:
                ask_vol = min(allowed_short, 15)
                self.ask(self.best_ask_price-1, ask_vol, orders)
                        
        #TOMATOES SKEW BASED LOGIC, DONT SKEW VOLUME SKEW PRICE
                    
        if self.product == "TOMATOES":
            allowed_long = POSITION_LIMITS.get(self.product) - self.current_position
            allowed_short = POSITION_LIMITS.get(self.product) + self.current_position #80 + -20 = 60 short osv

            ##TAKING ALL PROFITABLE
            for sp, sv in self.sell_orders.items():
                if sp < indicator:
                    allowed_long -= abs(sv)
                    self.bid(sp, sv, orders)
            
            for bp, bv in self.buy_orders.items():
                if bp > indicator:
                    allowed_short -= abs(bv)
                    self.ask(bp, bv, orders)

            #pos -> price effect simple asf because bots dont respond to tighter spread
            def calc_bid_price(allowed_short) -> int:
                if allowed_short < 40:
                    bid_price = indicator #zero edge 
                else:
                    bid_price = self.best_bid_price + 1 
                return int(bid_price)

            def calc_ask_price(allowed_long) -> int:
                if allowed_long < 40:
                    ask_price = indicator
                else: 
                    ask_price = self.best_ask_price - 1
                return int(ask_price)

            if int(self.best_bid_price + 1) < indicator:
                bid_price = calc_bid_price(allowed_short)
                self.bid(bid_price, allowed_long, orders)
            
            if int(self.best_ask_price - 1) > indicator:
                ask_price = calc_ask_price(allowed_long)
                self.ask(ask_price, allowed_short, orders)
        
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
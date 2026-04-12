import json
from typing import Literal
from datamodel import TradingState, Order

#POSITION LIMITS
POSITION_LIMITS = {
    "EMERALDS": 80,
    "TOMATOES": 180
}

#TECHNICALS
MA_WINDOW = 10

# --- GRID PARAMS ---
UNWIND_THRESHOLD_LONG = 10
UNWIND_THRESHOLD_SHORT = -10
TAKE_PROFIT_LONG = 20
TAKE_PROFIT_SHORT = -20
PRICE_OFFSET_ASK = 1
PRICE_OFFSET_BID = 1

ASK_SKEW1 = -1
ASK_SKEW2 = -2
ASK_SKEW_LEVEL2 = 65
ASK_SKEW_LEVEL1 = 50
BID_SKEW_LEVEL2 = -65
BID_SKEW_LEVEL1 = -50
BID_SKEW1 = 1
BID_SKEW2 = 2
# --- END GRID PARAMS ---

#SYMBOLS
Product = Literal["EMERALDS", "TOMATOES"]

class MarketTrader:
    def __init__(self, product, state):
        self.product = product 
        self.state = state 
        self.incoming_trader_data = self.get_trader_data()
        
        self.position_limit = POSITION_LIMITS.get(self.product.upper(), 0)
        self.current_position = self.state.position.get(self.product.upper(), 0) 

        self.best_bid_price, self.best_bid_volume = self.get_best_bid()
        self.best_ask_price, self.best_ask_volume = self.get_best_ask()
        self.buy_orders, self.sell_orders = self.get_order_depths()
        self.running_dhp, self.running_dhv, self.running_dlp, self.running_dlv = self.check_informed()

        self.wall_mid1 = self.compute_wallmid1()
        self.wall_mid2, self.td_key_wallmid = self.compute_wallmid2()
        self.wall_mid3 = self.compute_wallmid3()
        self.optimized_wallmid = self.compute_optimized_wallmid()
        
        self.outgoing_trader_data = self.get_outgoing_trader_data()
        self.wall_midma = self.compute_wallmidma() #needs outgoing TD for computation

    def get_trader_data(self) -> dict[str, dict]:
        if not self.state.traderData:
            return {
                "INFORMED_DATA": {"dh": [0, 0], "dl": [999999, 0]},
                "WALLMID_DATA": {}
            }
        
        return json.loads(self.state.traderData).get(self.product, {
            "INFORMED_DATA": {"dh": [0, 0], "dl": [999999, 0]},
            "WALLMID_DATA": {}
        })
                    
    def get_outgoing_trader_data(self) -> dict[str, dict]:
        assert self.incoming_trader_data, f"No trader data for: {self.product}"
        self.incoming_trader_data["WALLMID_DATA"][self.td_key_wallmid] = self.wall_mid2
        
        outgoing_trader_data = {
            "INFORMED_DATA": {
                "dh": (self.running_dhp, self.running_dhv),
                "dl": (self.running_dlp, self.running_dlv)
            },
            "WALLMID_DATA": self.incoming_trader_data["WALLMID_DATA"]
        }
        
        if len(outgoing_trader_data["WALLMID_DATA"]) > MA_WINDOW:
            old_key = next(iter(outgoing_trader_data["WALLMID_DATA"]))
            del outgoing_trader_data["WALLMID_DATA"][old_key]

        return outgoing_trader_data
        
    def check_informed(self) -> tuple[int, int, int, int]:
        prev_dhp, prev_dhv = self.incoming_trader_data["INFORMED_DATA"].get("dh")
        prev_dlp, prev_dlv = self.incoming_trader_data["INFORMED_DATA"].get("dl")

        trades = self.state.market_trades.get(self.product, [])
        if not trades:
            return prev_dhp, prev_dhv, prev_dlp, prev_dlv 

        else:
            _list = {}
            _list[prev_dhp] = prev_dhv
            _list[prev_dlp] = prev_dlv
            
            for trade in trades:
                _list[trade.price] = trade.quantity
            
            dh_price = max(max(prc for prc in _list.keys()), prev_dhp)
            dl_price = min(min(prc for prc in _list.keys()), prev_dlp)

            if dh_price == 999999:
                dh_price, dh_vol = trade.price, trade.quantity
                dl_price, dl_vol = trade.price, trade.quantity
            
            else:
                dh_vol = _list[dh_price]
                dl_vol = _list[dl_price]
            
            return dh_price, dh_vol, dl_price, dl_vol

    def bid(self, bp, bv, orders) -> None:
        if int(bv) == 0: 
            return
        orders.append(Order(self.product, bp, int(abs(bv))))

    def ask(self, sp, sv, orders) -> None:
        if int(sv) == 0: 
            return
        orders.append(Order(self.product, sp, int(-abs(sv))))
            
    def get_best_bid(self) -> tuple[int, int]:
        bbp, bbv = next(iter(self.state.order_depths[self.product].buy_orders.items()))
        return bbp, bbv
    
    def get_best_ask(self) -> tuple[int, int]:
        bap, bav = next(iter(self.state.order_depths[self.product].sell_orders.items()))
        return bap, bav #note BAV is negative
    
    def get_order_depths(self) -> tuple[dict[int, int], dict[int, int]]:
        depth = self.state.order_depths[self.product]
        return depth.buy_orders, depth.sell_orders

    def compute_wallmid1(self) -> float | None:
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
    
    def compute_wallmid2(self) -> tuple[float, str]:
        b_vols = list(self.buy_orders.values())
        s_vols = list(self.sell_orders.values())
        
        b_max = max(b_vols)
        s_max = min(s_vols)  
        
        b_prc = list(self.buy_orders.keys())[b_vols.index(b_max)]
        s_prc = list(self.sell_orders.keys())[s_vols.index(s_max)]
        
        wallmid = round((b_prc + s_prc) / 2, 2)
        key = f"{self.state.timestamp}_{self.product}"
    
        return wallmid, key
    
    def compute_wallmid3(self) -> float:
        buy_wall = min(prc for prc, _ in self.buy_orders.items())
        sell_wall = max(prc for prc, _ in self.sell_orders.items())
        wallmid = round((sell_wall + buy_wall) / 2, 2)
        
        return wallmid
    
    def compute_optimized_wallmid(self) -> float:
        ask, _ = self.get_best_ask()
        bid, _ = self.get_best_bid()
        mid = (ask+bid) / 2
        mid_offset = float(mid - self.wall_mid3)

        if abs(mid_offset) <= 0.5:
            fv = self.wall_mid3 + 0.734 * mid_offset
        else:
            fv = self.wall_mid3
        
        return fv
    
    def compute_wallmidma(self) -> float:
        window_data = []
        reversed_items = list(self.outgoing_trader_data.get("WALLMID_DATA", {}).items())[::-1]
        if len(self.outgoing_trader_data.get("WALLMID_DATA", {})) >= MA_WINDOW:
            for k, v in reversed_items:
                if str(self.product) in k:
                    window_data.append(v)
                    if len(window_data) == MA_WINDOW:
                        break
        
        if len(window_data) == MA_WINDOW:
            sme = round(sum(window_data) / len(window_data), 2)
            return sme


class InformedTaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)


class BasicMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, Order]:
        orders = []
    
        ##EMERALDS
        
        if self.product == "EMERALDS":
            # TAKING ALL PROFITABLE
            for sp, sv in self.sell_orders.items():
                if int(sp) < self.wall_mid3:
                    self.bid(sp, sv, orders)
            
            for bp, bv in self.buy_orders.items():
                if int(bp) > self.wall_mid3:
                    self.ask(bp, bv, orders)
            
            # MAKING REST
            skew_rate = self.current_position / self.position_limit 
        
            ask_price = self.best_ask_price - 1
            bid_price = self.best_bid_price + 1
            
            ask_price = max(ask_price, int(self.wall_mid3)) 
            bid_price = min(bid_price, int(self.wall_mid3))
                
            if int(self.best_ask_price - 1) > self.wall_mid3:
                vol_order = (self.position_limit - abs(self.current_position) / 2) * (1+skew_rate)
                self.ask(ask_price, vol_order, orders)
            
            if int(self.best_bid_price + 1) < self.wall_mid3:
                vol_order = (self.position_limit - abs(self.current_position) / 2) * (1-skew_rate)
                self.bid(bid_price, vol_order, orders)
        
        ##TOMATOES

        if self.product == "TOMATOES":
            
            # TAKING ALL PROFITABLE
            if self.current_position < TAKE_PROFIT_LONG:
                for sp, sv in self.sell_orders.items():
                    if int(sp) < self.optimized_wallmid:
                        self.bid(sp, sv, orders)
            
            if self.current_position > TAKE_PROFIT_SHORT:
                for bp, bv in self.buy_orders.items():
                    if int(bp) > self.optimized_wallmid:
                        self.ask(bp, bv, orders)

            #ACTIVE UNWINDING AT EDGE = 0
            if self.current_position > UNWIND_THRESHOLD_LONG:
                for bp, bv in self.buy_orders.items():
                    if int(bp) >= int(self.optimized_wallmid):
                        self.ask(bp, bv, orders)

            elif self.current_position < -UNWIND_THRESHOLD_SHORT:
                for sp, sv in self.sell_orders.items():
                    if int(sp) <= int(self.optimized_wallmid):
                        self.bid(sp, sv, orders)

            ##MAKING MARKET
            skew_rate = self.current_position / self.position_limit 
            match self.current_position:
                    case s if s > ASK_SKEW_LEVEL2:
                        ask_skew = ASK_SKEW2 #decrease ask to sell more
                    case s if s > ASK_SKEW_LEVEL1:
                        ask_skew = ASK_SKEW1
                    case _:
                        ask_skew = 0

            match self.current_position:
                case s if s < BID_SKEW_LEVEL2:
                    bid_skew = BID_SKEW2 #increase bid to buy more
                case s if s < BID_SKEW_LEVEL1:
                    bid_skew = BID_SKEW1
                case _:
                    bid_skew = 0
        
            ask_price = self.best_ask_price - PRICE_OFFSET_ASK + ask_skew
            bid_price = self.best_bid_price + PRICE_OFFSET_BID + bid_skew
            ask_price = max(ask_price, int(self.optimized_wallmid)) 
            bid_price = min(bid_price, int(self.optimized_wallmid))
                
            if int(self.best_ask_price - 1) > self.optimized_wallmid:
                vol_order = (self.position_limit - abs(self.current_position) / 2) * (1+skew_rate)
                self.ask(ask_price, vol_order, orders)
            
            if int(self.best_bid_price + 1) < self.optimized_wallmid:
                vol_order = (self.position_limit - abs(self.current_position) / 2) * (1-skew_rate)
                self.bid(bid_price, vol_order, orders)
            
        return {self.product: orders}
           
class Trader:

    def run(self, state: TradingState):
        result = {}
        logs = []
        outgoing = {}

        traders = {
            "TOMATOES": BasicMaker,
            "EMERALDS": BasicMaker
        }
        for product, TraderClass in traders.items():
            trader_instance = TraderClass(product, state)
            outgoing[product] = trader_instance.outgoing_trader_data

            orders = trader_instance.produce_orders()        
            product_orders = orders[product]
            logs.append([[o.symbol, o.price, o.quantity] for o in product_orders]) #for internal visualization tool of missed orders
            result.update(orders)
            
        conversions = 0
        traderData = json.dumps(outgoing)
        print(f"[DATA] {json.dumps({str(state.timestamp): logs})}")
        
        return result, conversions, traderData
        
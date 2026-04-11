import json
from typing import Literal
from datamodel import TradingState, Order

#POSITION LIMITS
POSITION_LIMITS = {
    "RAINFOREST_RESIN": 50,
    "KELP": 50,
    "SQUID_INK": 50
}

#TECHNICALS
MA_WINDOW = 10

#SYMBOLS
Product = Literal["RAINFOREST_RESIN", "KELP", "SQUID_INK"]

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
        
        self.dh_bid, self.dh_bid_vol, self.dl_ask, self.dl_ask_vol = self.informed_data()
        self.entered_trades = self.algo_history()

        self.wall_mid1 = self.compute_wallmid1()
        self.wall_mid2, self.td_key_wallmid = self.compute_wallmid2()
        self.wall_mid3 = self.compute_wallmid3()
        
        self.outgoing_trader_data = self.get_outgoing_trader_data()
        self.wall_midma = self.compute_wallmidma() 

    def get_trader_data(self) -> dict[str, dict]:
        if not self.state.traderData:
            return {
                "INFORMED_DATA": {
                    "prev_dl_ask": [0, 0], 
                    "prev_dh_bid": [0, 0],
                },
                "ENTERED_TRADES": {
                  "sell": [],
                  "buy": []  
                },
                "WALLMID_DATA": {}
            }
        
        return json.loads(self.state.traderData).get(self.product)
                    
    def get_outgoing_trader_data(self) -> dict[str, dict]:
        assert self.incoming_trader_data, f"No trader data for: {self.product}"
        self.incoming_trader_data["WALLMID_DATA"][self.td_key_wallmid] = self.wall_mid2
        
        outgoing_trader_data = {
            "INFORMED_DATA": {
                "prev_dl_ask": (self.dl_ask, self.dl_ask_vol),
                "prev_dh_bid": (self.dh_bid, self.dh_bid_vol),
            },
            "ENTERED_TRADES": self.entered_trades,
            "WALLMID_DATA": self.incoming_trader_data["WALLMID_DATA"]
        }
        
        if len(outgoing_trader_data["WALLMID_DATA"]) > MA_WINDOW:
            old_key = next(iter(outgoing_trader_data["WALLMID_DATA"]))
            del outgoing_trader_data["WALLMID_DATA"][old_key]

        return outgoing_trader_data
    
    #very important mention! technically speaking we can save literally every trade we do
    #BUT if running an trade heavy strat this will get 1000s of items long, this is still 
    #more than fast enough to clear the 900 ms / run limit but dreadfully slow for sims

    def algo_history(self) -> dict[str, dict[str, list[int, int]]]:
        time = self.state.timestamp
        if time == 0:
            entered_trades = {}
            entered_trades["sell"] = [{time : [0,0]}]
            entered_trades["buy"] = [{time : [0,0]}]
        else:
            entered_trades = self.incoming_trader_data["ENTERED_TRADES"]
            if self.product in self.state.own_trades.keys():
                new_trades = self.state.own_trades[self.product]
                for trade in new_trades:
                    if trade.seller == "SUBMISSION":    
                        entered_trades["sell"].append({time: [trade.quantity, trade.price]})  
                    elif trade.buyer == "SUBMISSION":
                        entered_trades["buy"].append({time: [trade.quantity, trade.price]})
        
        if len(entered_trades["sell"]) > 20:
            del entered_trades["sell"][0]
        
        if len(entered_trades["buy"]) > 20:
            del entered_trades["buy"][0]

        return entered_trades

    def informed_data(self) -> tuple[int, int, int, int]:
        ask, askv = self.get_best_ask()
        bid, bidv = self.get_best_bid()
        
        if self.state.timestamp == 0:
            prev_dl_ask, prev_dl_ask_vol = ask, askv
            prev_dh_bid, prev_dh_bid_vol = bid, bidv
            
        else:
            prev_dl_ask, prev_dl_ask_vol = self.incoming_trader_data["INFORMED_DATA"]["prev_dl_ask"]
            prev_dh_bid, prev_dh_bid_vol = self.incoming_trader_data["INFORMED_DATA"]["prev_dh_bid"]
            if ask < prev_dl_ask:
                prev_dl_ask, prev_dl_ask_vol = ask, askv
            if bid > prev_dh_bid:
                prev_dh_bid, prev_dh_bid_vol = bid, bidv

        return prev_dh_bid, prev_dh_bid_vol, prev_dl_ask, prev_dl_ask_vol

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

    def produce_orders(self) -> dict[Product, Order]:
        orders = []
        sus_vol = 15
        tolerance = 1

        prev_dl_ask, prev_dl_ask_vol = self.incoming_trader_data["INFORMED_DATA"]["prev_dl_ask"]
        prev_dh_bid, prev_dh_bid_vol = self.incoming_trader_data["INFORMED_DATA"]["prev_dh_bid"]

        #take at dh/dl -> note a small specific entered_trades can have multiple trades for each timestamp
        #but when running this strat specifically we know that it wont
        if self.product in self.state.market_trades.keys():
            for trade in self.state.market_trades[self.product]:
                if trade.quantity == sus_vol:
                    if trade.price - tolerance <= prev_dl_ask: 
                        self.bid(self.best_ask_price, 20, orders)
                        
                    elif trade.price + tolerance >= prev_dh_bid:
                        self.ask(self.best_bid_price, 20, orders)
                        
        #reverse prev false signal trades -> notice we take at spread to escape position
        if self.best_ask_price + 1 < prev_dl_ask:
            try: 
                if self.incoming_trader_data["ENTERED_TRADES"]["sell"][0]: #we only have one l/s at a time!
                    self.bid(self.best_ask_price, 20, orders)
            except IndexError:
                pass
        elif self.best_bid_price - 1 > prev_dh_bid:
            try:
                if self.incoming_trader_data["ENTERED_TRADES"]["buy"][0]:
                    self.ask(self.best_bid_price, 20, orders)
            except IndexError:
                pass
            
        return {self.product: orders}            

class BasicMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, Order]:
        orders = []
    
        ##TAKING ALL PROFITABLE
        for sp, sv in self.sell_orders.items():
            if int(sp) < self.wall_mid3:
                self.bid(sp, sv, orders)
        
        for bp, bv in self.buy_orders.items():
            if int(bp) > self.wall_mid3:
                self.ask(bp, bv, orders)
        
        #ACTIVE UNWINDING AT EDGE = 0
        if self.current_position > 50:
            for sp, sv in self.sell_orders.items():
                if int(sp) <= self.wall_mid3:
                    self.bid(sp, sv, orders)
        
            for bp, bv in self.buy_orders.items():
                if int(bp) >= self.wall_mid3:
                    self.ask(bp, bv, orders)

        ##MAKING MARKET
        skew_rate = self.current_position / self.position_limit 
        
        match self.current_position:
            case s if s > 65:
                ask_skew = -2 #decrease ask to sell more
            case s if s > 50:
                ask_skew = -1
            case _:
                ask_skew = 0

        match self.current_position:
            case s if s < -65:
                bid_skew = 2 #increase bid to buy more
            case s if s < -50:
                bid_skew = 1
            case _:
                bid_skew = 0
        
        ask_price = self.best_ask_price - 1 + ask_skew
        bid_price = self.best_bid_price + 1 + bid_skew
        ask_price = max(ask_price, int(self.wall_mid3)) 
        bid_price = min(bid_price, int(self.wall_mid3))
            
        if int(self.best_ask_price - 1) > self.wall_mid3:
            vol_order = (self.position_limit - abs(self.current_position) / 2) * (1+skew_rate)
            self.ask(ask_price, vol_order, orders)
        
        if int(self.best_bid_price + 1) < self.wall_mid3:
            vol_order = (self.position_limit - abs(self.current_position) / 2) * (1-skew_rate)
            self.bid(bid_price, vol_order, orders)
            
        return {self.product: orders}
           
class Trader:

    def run(self, state: TradingState):
        result = {}
        logs = []
        outgoing = {}

        traders = {
            "RAINFOREST_RESIN": BasicMaker,
            "KELP": BasicMaker,
            "SQUID_INK": InformedTaker
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
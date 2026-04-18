import json
import numpy as np
from dataclasses import dataclass, field
from typing import Literal
from datamodel import TradingState, Order

Product = Literal["INTARIAN_PEPPER_ROOT", "ASH_COATED_OSMIUM"]

POSITION_LIMITS = {"INTARIAN_PEPPER_ROOT": 80, "ASH_COATED_OSMIUM": 80}

ACO_UNWIND_THRESHOLD = 15
ACO_TAKE_PROFIT = 30
ACO_PRICE_OFFSET = 1
ACO_PRC_SKEW1 = 1
ACO_PRC_SKEW2 = 2
ACO_SKEW_LEVEL2 = 65
ACO_SKEW_LEVEL1 = 50
ACO_MA_WINDOW = 10

IPR_MIN_LONG = 75
IPR_MIN_SHORT = -75
IPR_REGWALL_INTERCEPT = round((12006.876025527785 + 11993.144067190733) / 2, 2)
IPR_REGWALL_SLOPE = 0.1
IPR_REGWALL_SAFETY_MARGIN = 3
IPR_REGWALL_SAFETY_SLOPE = 0.03

@dataclass
class AlgoTrade:
    timestamp: str
    quantity: int
    price: int
    buyer: str | None
    seller: str | None
    
@dataclass 
class PlacedOrder:
    timestamp: str
    quantity: int
    price: int
    buyer: str | None
    seller: str | None 

@dataclass 
class InformedData:
    ask_history: list[int] = field(default_factory=list)
    bid_history: list[int] = field(default_factory=list)
    current_slope: float | None = None

@dataclass 
class MaData:
    wallmid_history: list[float] = field(default_factory=list)

@dataclass
class TraderData:
    informed_data: InformedData = field(default_factory=InformedData)
    ma_data: MaData = field(default_factory=MaData)
    algo_trades: list[AlgoTrade] = field(default_factory=list)
    placed_orders: list[PlacedOrder] = field(default_factory=list)


class MarketTrader:
    def __init__(self, product, state):
        self.product = product 
        self.state = state 
        self.trader_data = self.get_trader_data()
        self.append_algo_trades()
    
        self.position_limit = POSITION_LIMITS.get(self.product.upper(), 0)
        self.current_position = self.state.position.get(self.product.upper(), 0) 

        self.buy_orders, self.sell_orders = self.get_order_depths()
        self.has_book = bool(self.buy_orders) and bool(self.sell_orders)
        if not self.has_book:
            return

        self.best_bid_price, self.best_bid_volume = self.get_best_bid()
        self.best_ask_price, self.best_ask_volume = self.get_best_ask()
        
        self.effective_mid = self.compute_wallmid()
        self.append_wallmid_history()
        self.wallmid_ma = self.compute_wallmidma()
        self.effective_mid = self.wallmid_ma if self.wallmid_ma is not None else self.effective_mid
        
        if self.product == "INTARIAN_PEPPER_ROOT":
            self.append_regwall_data()
            self.regwall, _ = self.compute_regwall()
            if not self.check_regwall(): self.regwall, self.trader_data.informed_data.current_slope = self.compute_regwall() #regwall ok against historical estimate
            else: self.regwall, self.trader_data.informed_data.current_slope = self.check_regwall()
    
    def get_trader_data(self) -> TraderData:
        if not self.state.traderData: return TraderData()
        decoded = self.decode_trader_data(self.state.traderData, self.product)
        return decoded
    
    def decode_trader_data(self, raw_str: str, product: str) -> TraderData:
        d = json.loads(raw_str).get(product)
        if not d:
            return TraderData()
        td = TraderData()
        td.informed_data.ask_history = d["informed_data"]["ask_history"]
        td.informed_data.bid_history = d["informed_data"]["bid_history"]
        td.informed_data.current_slope = d["informed_data"]["current_slope"]
        td.ma_data.wallmid_history = d.get("ma_data", {}).get("wallmid_history", [])
        td.algo_trades = [AlgoTrade(**t) for t in d.get("algo_trades", [])]
        return td
    
    def append_algo_trades(self) -> None:
        incoming = self.state.own_trades.get(self.product, 0)
        if incoming != 0:
            for trade in self.state.own_trades[self.product]:
                self.trader_data.algo_trades.append(AlgoTrade(
                    timestamp=str(self.state.timestamp-100),
                    quantity=trade.quantity,
                    price=trade.price,
                    buyer="SUBMISSION" if trade.buyer == "SUBMISSION" else "",
                    seller="SUBMISSION" if trade.seller == "SUBMISSION" else ""
                ))
        
        if len(self.trader_data.algo_trades) > 5:
            self.trader_data.algo_trades = self.trader_data.algo_trades[-5:]

    def bid(self, bp, bv, orders) -> None:
        if int(bv) == 0: 
            return
        orders.append(Order(self.product, bp, int(abs(bv))))

    def ask(self, sp, sv, orders) -> None:
        if int(sv) == 0: 
            return
        orders.append(Order(self.product, sp, int(-abs(sv))))
            
    def get_best_bid(self) -> tuple[int, int]:
        return next(iter(self.buy_orders.items()))

    def get_best_ask(self) -> tuple[int, int]:
        return next(iter(self.sell_orders.items())) #note volume is negative
    
    def get_order_depths(self) -> tuple[dict[int, int], dict[int, int]]:
        if self.product not in self.state.order_depths:
            return {}, {}
        depth = self.state.order_depths[self.product]
        return depth.buy_orders, depth.sell_orders

    def compute_wallmid(self) -> float:
        buy_wall = min(prc for prc, _ in self.buy_orders.items())
        sell_wall = max(prc for prc, _ in self.sell_orders.items())
        wallmid = round((sell_wall + buy_wall) / 2, 2)
        return wallmid
    
    def append_wallmid_history(self) -> None:
        self.trader_data.ma_data.wallmid_history.append(self.effective_mid)
        if len(self.trader_data.ma_data.wallmid_history) > ACO_MA_WINDOW * 2:
            self.trader_data.ma_data.wallmid_history = self.trader_data.ma_data.wallmid_history[-ACO_MA_WINDOW:]

    def compute_wallmidma(self) -> float | None:
        history = self.trader_data.ma_data.wallmid_history
        if len(history) >= ACO_MA_WINDOW:
            window = history[-ACO_MA_WINDOW:]
            return round(sum(window) / len(window), 2)
        return None
    
    def compute_regwall(self) -> float:
        regwall = IPR_REGWALL_INTERCEPT + IPR_REGWALL_SLOPE * (self.state.timestamp / 100)
        return regwall, IPR_REGWALL_SLOPE

    def append_regwall_data(self) -> None:
        if not self.best_ask_price:
            if self.trader_data.informed_data.ask_history:
                self.trader_data.informed_data.ask_history.append(self.trader_data.informed_data.ask_history[-1])
        else:            
            self.trader_data.informed_data.ask_history.append(self.best_ask_price)
        
        if not self.best_bid_price:
            if self.trader_data.informed_data.bid_history:
                self.trader_data.informed_data.bid_history.append(self.trader_data.informed_data.bid_history[-1]) 
        else:
            self.trader_data.informed_data.bid_history.append(self.best_bid_price)
        
        if len(self.trader_data.informed_data.ask_history) > 200:
            self.trader_data.informed_data.ask_history = self.trader_data.informed_data.ask_history[-150:]
        
        if len(self.trader_data.informed_data.bid_history) > 200:
            self.trader_data.informed_data.bid_history = self.trader_data.informed_data.bid_history[-150:]

    def check_regwall(self) -> bool | list[bool, float | None]:
        if len(self.trader_data.informed_data.ask_history) >= 100 and len(self.trader_data.informed_data.bid_history) >= 100:
            available_len = min(len(self.trader_data.informed_data.ask_history), len(self.trader_data.informed_data.bid_history))
            X = [i for i in range(1, available_len+1)]
            X = np.column_stack([np.ones(len(X)), X]) #create a 2D array for the reg
            
            Ya = np.array(self.trader_data.informed_data.ask_history[:available_len])
            Yb = np.array(self.trader_data.informed_data.bid_history[:available_len])
            beta_a = np.linalg.lstsq(X, Ya, rcond=None)[0] 
            beta_b = np.linalg.lstsq(X, Yb, rcond=None)[0]
            
            computed_regwall_intercept = (beta_a[0] + beta_b[0]) / 2
            computed_regwall_slope_a = round(beta_a[1], 2) #if this is as we think
            computed_regwall_slope_b = round(beta_b[1], 2) #both should round to 0.1!
            
            avg_slope = round((computed_regwall_slope_a + computed_regwall_slope_b) / 2, 2)
            computed_regwall = computed_regwall_intercept + computed_regwall_slope_a * X[-1, 1] #col 1 "time data"

            if abs(computed_regwall_slope_a - computed_regwall_slope_b) < IPR_REGWALL_SAFETY_SLOPE:
                if abs(self.regwall - computed_regwall) < IPR_REGWALL_SAFETY_MARGIN: return False #OK
                else:
                    return computed_regwall, avg_slope #not ok return new regwall we are certain about new SLOPE
            else:
                return computed_regwall, None #very bad slopes do not match algo is stale  
        else: return False #cant mark as false just because data is missing


class InformedMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, Order]:
        orders = []
        if not self.has_book:
            return {self.product: orders}

        # TAKING ALL PROFITABLE
        if self.current_position < ACO_TAKE_PROFIT:
            for sp, sv in self.sell_orders.items():
                if int(sp) < self.effective_mid:
                    self.bid(sp, sv, orders)
        
        if self.current_position > -ACO_TAKE_PROFIT:
            for bp, bv in self.buy_orders.items():
                if int(bp) > self.effective_mid:
                    self.ask(bp, bv, orders)

        #ACTIVE UNWINDING AT EDGE = 0
        if self.current_position > ACO_UNWIND_THRESHOLD:
            for bp, bv in self.buy_orders.items():
                if int(bp) >= int(self.effective_mid):
                    self.ask(bp, bv, orders)

        elif self.current_position < -ACO_UNWIND_THRESHOLD:
            for sp, sv in self.sell_orders.items():
                if int(sp) <= int(self.effective_mid):
                    self.bid(sp, sv, orders)

        ##MAKING MARKET
        skew_rate = self.current_position / self.position_limit 
        match self.current_position:
                case s if s > ACO_SKEW_LEVEL2:
                    ask_skew = -ACO_PRC_SKEW2 #decrease ask to sell more
                case s if s > ACO_SKEW_LEVEL1:
                    ask_skew = -ACO_PRC_SKEW1
                case _:
                    ask_skew = 0

        match self.current_position:
            case s if s < -ACO_SKEW_LEVEL2:
                bid_skew = ACO_PRC_SKEW2 #increase bid to buy more
            case s if s < -ACO_SKEW_LEVEL1:
                bid_skew = ACO_PRC_SKEW1
            case _:
                bid_skew = 0
    
        ask_price = self.best_ask_price - ACO_PRICE_OFFSET + ask_skew
        bid_price = self.best_bid_price + ACO_PRICE_OFFSET + bid_skew
        ask_price = max(ask_price, int(self.effective_mid)) 
        bid_price = min(bid_price, int(self.effective_mid))
            
        if int(self.best_ask_price - 1) > self.effective_mid:
            vol_order = ((self.position_limit - abs(self.current_position)) / 2) * (1+skew_rate)
            self.ask(ask_price, vol_order, orders)
        
        if int(self.best_bid_price + 1) < self.effective_mid:
            vol_order = ((self.position_limit - abs(self.current_position)) / 2) * (1-skew_rate)
            self.bid(bid_price, vol_order, orders)
        
        return {self.product: orders}


class BasicMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, Order]:
        orders = []
        if not self.has_book:
            return {self.product: orders}
        
        allowed_short = POSITION_LIMITS["INTARIAN_PEPPER_ROOT"] + self.current_position
        allowed_long = POSITION_LIMITS["INTARIAN_PEPPER_ROOT"] - self.current_position
        current_slope = self.trader_data.informed_data.current_slope

        #CHECK if IN EXPECTED TREND or NOT
        if not current_slope:
            return {self.product: orders}
        
        if current_slope > 0.0:
            if self.current_position < IPR_MIN_LONG: 
                allowed_short = 0 
        
        elif current_slope < 0.0:
            if self.current_position > IPR_MIN_SHORT:
                allowed_long = 0
        
        # TAKING ALL PROFITABLE
        for sp, sv in self.sell_orders.items():
            if int(sp) < self.regwall:
                vol = min(abs(sv), allowed_long)
                self.bid(sp, vol, orders)
                allowed_long -= vol
        
        for bp, bv in self.buy_orders.items():
            if int(bp) > self.regwall:
                vol = min(bv, allowed_short)
                self.ask(bp, vol, orders)
                allowed_short -= vol
        
        # MAKING REST
        if current_slope > 0.0:
            if self.current_position < IPR_MIN_LONG and self.state.timestamp < 20000:
                bid_price = self.best_ask_price
                if allowed_long > 0:
                    self.bid(bid_price, allowed_long, orders)

            elif self.current_position < IPR_MIN_LONG:
                bid_price = self.best_bid_price + 2
                if allowed_long > 0 and bid_price + 1 < self.regwall:
                    self.bid(bid_price, allowed_long, orders)

            else:
                bid_price = min(self.best_bid_price + 1, int(self.regwall))
                if allowed_long > 0 and bid_price + 1 < self.regwall:
                    self.bid(bid_price, allowed_long, orders)

            ask_price = max(self.best_ask_price, int(self.regwall))
            if allowed_short > 0 and ask_price - 1 > self.regwall:
                self.ask(ask_price, allowed_short, orders)

        elif current_slope < 0.0:
            if self.current_position > IPR_MIN_SHORT and self.state.timestamp < 20000:
                ask_price = self.best_bid_price
                if allowed_short > 0:
                    self.ask(ask_price, allowed_short, orders)

            elif self.current_position > IPR_MIN_SHORT:
                ask_price = self.best_ask_price + 2
                if allowed_short > 0 and ask_price - 1 > self.regwall:
                    self.ask(ask_price, allowed_short, orders)

            else:
                ask_price = max(self.best_ask_price + 1, int(self.regwall))
                if allowed_short > 0 and ask_price - 1 > self.regwall:
                    self.ask(ask_price, allowed_short, orders)

            bid_price = min(self.best_bid_price, int(self.regwall))
            if allowed_long > 0 and bid_price + 1 < self.regwall:
                self.bid(bid_price, allowed_long, orders)
            
        return {self.product: orders}


class Trader:

    def encode_trader_data(self, outgoing: dict) -> str:
        raw = {}
        for product, td in outgoing.items():
            raw[product] = {
                "informed_data": {
                    "ask_history": td.informed_data.ask_history,
                    "bid_history": td.informed_data.bid_history,
                    "current_slope": td.informed_data.current_slope,
                },
                "ma_data": {
                    "wallmid_history": td.ma_data.wallmid_history,
                },
                "algo_trades": [
                    {"timestamp": t.timestamp, "quantity": t.quantity, "price": t.price,
                    "buyer": t.buyer, "seller": t.seller}
                    for t in td.algo_trades
                ],
            }
        return json.dumps(raw)

    def run(self, state: TradingState):
        result = {}
        logs = []
        outgoing = {}

        traders = {
            "ASH_COATED_OSMIUM": InformedMaker,
            "INTARIAN_PEPPER_ROOT": BasicMaker
        }
        for product, TraderClass in traders.items():
            trader_instance = TraderClass(product, state)
            outgoing[product] = trader_instance.trader_data

            orders = trader_instance.produce_orders()        
            product_orders = orders[product]
            logs.append([[o.symbol, o.price, o.quantity] for o in product_orders]) #for internal visualization tool of missed orders
            result.update(orders)
            
        conversions = 0
        traderData = self.encode_trader_data(outgoing)
        print(f"[DATA] {json.dumps({str(state.timestamp): logs})}")
        
        return result, conversions, traderData
        
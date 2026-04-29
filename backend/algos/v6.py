import json
from dataclasses import dataclass, field
from typing import Literal, cast
from datamodel import Order, TradingState

Product = Literal["self.wall_mid", 
                "VELVETFRUIT_EXTRACT", 
                "VEV_4000",
                "VEV_4500",
                "VEV_5000",
                "VEV_5100",
                "VEV_5200",
                "VEV_5300",
                "VEV_5400",
                "VEV_5500",
                "VEV_6000",
                "VEV_6500",
                ]

POSITION_LIMITS = {
    "HYDROGEL_PACK": 200, 
    "VELVETFRUIT_EXTRACT": 200, 
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
    "VEV_6000": 300,
    "VEV_6500": 300,
    }

ENTRY_Z = 1.5
EXIT_Z = 0.25

HP_EQUILIBRIUM = round(9990.571806076006, 2)
HP_SIGMA = round(30.78900918189155, 2)

@dataclass
class TraderData:
    data: int = 0

class MarketTrader:
    def __init__(self, product, state):
        self.product = product 
        self.state = state 
        self.trader_data = self.get_trader_data()
        
        self.position_limit = POSITION_LIMITS.get(self.product.upper(), 0)
        self.current_position = self.state.position.get(self.product.upper(), 0) 

        self.buy_orders, self.sell_orders = self.get_order_depths()
        self.has_book = bool(self.buy_orders) and bool(self.sell_orders)
        if not self.has_book:
            return

        self.best_bid_price, self.best_bid_volume = self.get_best_bid()
        self.best_ask_price, self.best_ask_volume = self.get_best_ask()
        
        self.wall_mid = self.compute_wallmid()
        self.zscore = self.compute_z()
        
    def get_trader_data(self) -> TraderData:
        if not self.state.traderData: 
            return TraderData()
        decoded = self.decode_trader_data(self.state.traderData, self.product)
        return decoded
    
    def decode_trader_data(self, raw_str: str, product: str) -> TraderData:
        d = json.loads(raw_str).get(product)
        if not d:
            return TraderData()
        td = TraderData()
        td.data = d["data"]
        return td
    
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

    def compute_z(self) -> float:
        z_score = (self.wall_mid - HP_EQUILIBRIUM) / HP_SIGMA
        return z_score
    
class MarketMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, list[Order]]:
        orders: list[Order] = []
        if not self.has_book:
            return {self.product: orders}

        allowed_long = self.position_limit - self.current_position
        allowed_short = self.position_limit + self.current_position

        if self.zscore > ENTRY_Z and self.current_position <= 0:
            for bp, bv in self.buy_orders.items():
                vol = min(bv, allowed_short)
                self.ask(bp, vol, orders)
                allowed_short -= vol
                if allowed_short <= 0:
                    break
        elif self.zscore < -ENTRY_Z and self.current_position >= 0:
            for sp, sv in self.sell_orders.items():
                vol = min(abs(sv), allowed_long)
                self.bid(sp, vol, orders)
                allowed_long -= vol
                if allowed_long <= 0:
                    break
        elif abs(self.zscore) < EXIT_Z and self.current_position != 0:
            if self.current_position > 0:
                remaining = self.current_position
                for bp, bv in self.buy_orders.items():
                    vol = min(bv, remaining)
                    self.ask(bp, vol, orders)
                    remaining -= vol
                    if remaining <= 0:
                        break
            else:
                remaining = -self.current_position
                for sp, sv in self.sell_orders.items():
                    vol = min(abs(sv), remaining)
                    self.bid(sp, vol, orders)
                    remaining -= vol
                    if remaining <= 0:
                        break

        return {self.product: orders}

class OptionsTrader(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)
        
    def produce_orders(self) -> dict[Product, list[Order]]:
        orders: list[Order] = []
        if not self.has_book:
            return {self.product: orders}

        return {self.product: orders}

class Trader:

    def encode_trader_data(self, outgoing: dict) -> str:
        raw = {}
        for product, td in outgoing.items():
            raw[product] = {
                "data": td.data
            }
        return json.dumps(raw)

    def run(self, state: TradingState):
        result = {}
        logs = []
        outgoing = {}

        traders = cast(dict[Product, type[MarketMaker | OptionsTrader]], {
            "HYDROGEL_PACK": MarketMaker,
            "VELVETFRUIT_EXTRACT": MarketMaker,
            "VEV_4000": OptionsTrader,
            "VEV_4500": OptionsTrader,
            "VEV_5000": OptionsTrader,
            "VEV_5100": OptionsTrader,
            "VEV_5200": OptionsTrader,
            "VEV_5300": OptionsTrader,
            "VEV_5400": OptionsTrader,
            "VEV_5500": OptionsTrader,
            "VEV_6000": OptionsTrader,
            "VEV_6500": OptionsTrader,
        })
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
        
import jsonpickle
from dataclasses import dataclass, field
from typing import Literal
from datamodel import TradingState, Order

POSITION_LIMITS = {"EMERALDS": 80, "TOMATOES": 80}
TOLERANCE = 2
SUSVOL = 6
Product = Literal["EMERALDS", "TOMATOES"]

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
    dh_ask_price: int = 0
 
@dataclass 
class TraderData:
    informed_data: InformedData = field(default_factory=InformedData)
    algo_trades: list[AlgoTrade] = field(default_factory=list)
    placed_orders: list[PlacedOrder] = field(default_factory=list)


class MarketTrader:
    def __init__(self, product, state):
        self.product = product 
        self.state = state 
        self.trader_data = self.get_trader_data()

        self.position_limit = POSITION_LIMITS.get(self.product.upper(), 0)
        self.current_position = self.state.position.get(self.product.upper(), 0) 

        self.best_bid_price, self.best_bid_volume = self.get_best_bid()
        self.best_ask_price, self.best_ask_volume = self.get_best_ask()
        self.buy_orders, self.sell_orders = self.get_order_depths()
        
        self.wall_mid = self.compute_wallmid()
        self.optimized_wallmid = self.compute_optimized_wallmid()
    
    def get_trader_data(self) -> TraderData:
        if not self.state.traderData: return TraderData()
        decoded = jsonpickle.decode(self.state.traderData)
        return decoded.get(self.product, TraderData())
    
    def append_algo_trades(self) -> None:
        incoming = self.state.own_trades.get(self.product, 0)
        if incoming != 0:
            for trade in self.state.own_trades[self.product]:
                self.trader_data.algo_trades.append(AlgoTrade(
                    timestamp=self.state.timestamp-100,
                    quantity=trade.quantity,
                    price=trade.price,
                    buyer="SUBMISSION" if trade.buyer == "SUBMISSION" else "",
                    seller="SUBMISSION" if trade.seller == "SUBMISSION" else ""
                ))

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

    def compute_wallmid(self) -> float:
        buy_wall = min(prc for prc, _ in self.buy_orders.items())
        sell_wall = max(prc for prc, _ in self.sell_orders.items())
        wallmid = round((sell_wall + buy_wall) / 2, 2)
        
        return wallmid
    
    def compute_optimized_wallmid(self) -> float:
        ask, _ = self.get_best_ask()
        bid, _ = self.get_best_bid()
        mid = (ask+bid) / 2
        mid_offset = float(mid - self.wall_mid)

        if abs(mid_offset) <= 0.5:
            fv = self.wall_mid + 0.734 * mid_offset
        else:
            fv = self.wall_mid
        
        return fv


class InformedTaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, Order]:
        orders = []

        #IF sus trade detected we act on it
        for trade in self.state.market_trades.get(self.product, []):
            if trade.quantity == SUSVOL:
                self.ask(self.best_bid_price, 80, orders)
                self.trader_data.placed_orders.append(PlacedOrder(
                    timestamp=str(self.state.timestamp),
                    quantity=80,
                    price=self.best_bid_price,
                    buyer="",
                    seller="SUBMISSION"
                ))
        
        #IF only a small fill the first time we need to act again until position is full SHORT
        current_pos = self.state.position.get(self.product, 0)
        achieved_short = 0 

        for algotrade in self.trader_data.algo_trades:
             achieved_short += algotrade.quantity if algotrade.seller == "SUBMISSION" else 0
        
        remaining_short = 80 + current_pos - achieved_short
        if remaining_short > 0:
            self.ask(self.best_bid_price, remaining_short, orders)
            self.trader_data.placed_orders.append(PlacedOrder(
                timestamp=str(self.state.timestamp),
                quantity=remaining_short,
                price=self.best_bid_price,
                buyer="",
                seller="SUBMISSION"
            ))
                            
        return {self.product: orders}


class BasicMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, Order]:
        orders = []
        
        # TAKING ALL PROFITABLE
        for sp, sv in self.sell_orders.items():
            if int(sp) < self.wall_mid:
                self.bid(sp, sv, orders)
        
        for bp, bv in self.buy_orders.items():
            if int(bp) > self.wall_mid:
                self.ask(bp, bv, orders)
        
        # MAKING REST
        skew_rate = self.current_position / self.position_limit 
    
        ask_price = self.best_ask_price - 1
        bid_price = self.best_bid_price + 1
        
        ask_price = max(ask_price, int(self.wall_mid)) 
        bid_price = min(bid_price, int(self.wall_mid))
            
        if int(self.best_ask_price - 1) > self.wall_mid:
            vol_order = (self.position_limit - abs(self.current_position) / 2) * (1+skew_rate)
            self.ask(ask_price, vol_order, orders)
        
        if int(self.best_bid_price + 1) < self.wall_mid:
            vol_order = (self.position_limit - abs(self.current_position) / 2) * (1-skew_rate)
            self.bid(bid_price, vol_order, orders)
        
        return {self.product: orders}


class Trader:

    def run(self, state: TradingState):
        result = {}
        logs = []
        outgoing = {}

        traders = {
            "TOMATOES": InformedTaker,
            "EMERALDS": BasicMaker
        }
        for product, TraderClass in traders.items():
            trader_instance = TraderClass(product, state)
            outgoing[product] = trader_instance.trader_data

            orders = trader_instance.produce_orders()        
            product_orders = orders[product]
            logs.append([[o.symbol, o.price, o.quantity] for o in product_orders]) #for internal visualization tool of missed orders
            result.update(orders)
            
        conversions = 0
        traderData = jsonpickle.dumps(outgoing)
        print(f"[DATA] {jsonpickle.dumps({str(state.timestamp): logs})}")
        
        return result, conversions, traderData
        
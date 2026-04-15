import jsonpickle
from dataclasses import dataclass, field
from typing import Literal
from datamodel import TradingState, Order

POSITION_LIMITS = {"INTARIAN_PEPPER_ROOT": 80, "ASH_COATED_OSMIUM": 80}

TOLERANCE = 2
SUSVOL = 6

UNWIND_THRESHOLD_LONG = 10
UNWIND_THRESHOLD_SHORT = -10
TAKE_PROFIT_LONG = 20
TAKE_PROFIT_SHORT = -20
PRICE_OFFSET_ASK = 1
PRICE_OFFSET_BID = 1

ASK_SKEW1 = -1
ASK_SKEW2 = -2
BID_SKEW1 = 1
BID_SKEW2 = 2
ASK_SKEW_LEVEL2 = 65
ASK_SKEW_LEVEL1 = 50
BID_SKEW_LEVEL2 = -65
BID_SKEW_LEVEL1 = -50


Product = Literal["INTARIAN_PEPPER_ROOT", "ASK_COATED_OSMIUM"]

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
    short_triggered: bool = False
    short_triggered_at: int = 0
    market_make: bool = True
 
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
        self.append_algo_trades()

        self.position_limit = POSITION_LIMITS.get(self.product.upper(), 0)
        self.current_position = self.state.position.get(self.product.upper(), 0) 

        self.buy_orders, self.sell_orders = self.get_order_depths()
        self.has_book = bool(self.buy_orders) and bool(self.sell_orders)
        if not self.has_book:
            return

        self.best_bid_price, self.best_bid_volume = self.get_best_bid()
        self.best_ask_price, self.best_ask_volume = self.get_best_ask()
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
        
        if len(self.trader_data.algo_trades) > 20:
            self.trader_data.algo_trades = self.trader_data.algo_trades[-20:]

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


class InformedMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, Order]:
        orders = []
        if not self.has_book:
            return {self.product: orders}

        #business as usual
        if self.trader_data.informed_data.market_make:
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

            elif self.current_position < UNWIND_THRESHOLD_SHORT:
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
            
            #IF sus trade detected we act on it and stop market making
            for trade in self.state.market_trades.get(self.product, []):
                if trade.quantity == SUSVOL:
                    self.ask(self.best_bid_price, 80, orders)
                    self.trader_data.informed_data.short_triggered = True
                    self.trader_data.informed_data.market_make = False
                    self.trader_data.informed_data.short_triggered_at = self.state.timestamp
                    """self.trader_data.placed_orders.append(PlacedOrder(
                        timestamp=str(self.state.timestamp),
                        quantity=80,
                        price=self.best_bid_price,
                        buyer="",
                        seller="SUBMISSION"
                    ))"""
        
        #shorting period
        elif not self.trader_data.informed_data.market_make:        
            #Short period has ended take profit
            if self.trader_data.informed_data.short_triggered:
                if self.trader_data.informed_data.short_triggered_at == self.state.timestamp-100000:
                    self.trader_data.informed_data.market_make = True
        
            #IF only a small fill the first time we need to act again until position is full SHORT
            if self.trader_data.informed_data.short_triggered:
                current_pos = self.state.position.get(self.product, 0)

                if current_pos > -POSITION_LIMITS["ASH_COATED_OSMIUM"]:
                    remaining_short = POSITION_LIMITS["ASH_COATED_OSMIUM"] + current_pos
                    self.ask(self.best_bid_price, remaining_short, orders)
                    """self.trader_data.placed_orders.append(PlacedOrder(
                        timestamp=str(self.state.timestamp),
                        quantity=remaining_short,
                        price=self.best_bid_price,
                        buyer="",
                        seller="SUBMISSION"
                    ))"""
        
        return {self.product: orders}


class BasicMaker(MarketTrader):
    def __init__(self, product, state):
        super().__init__(product, state)

    def produce_orders(self) -> dict[Product, Order]:
        orders = []
        if not self.has_book:
            return {self.product: orders}

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
        traderData = jsonpickle.dumps(outgoing)
        print(f"[DATA] {jsonpickle.dumps({str(state.timestamp): logs})}")
        
        return result, conversions, traderData
        
import json
from dataclasses import dataclass
from typing import Literal, cast

from datamodel import Order, TradingState

# ---------------- Constants ---------------- #

Product = Literal[
    "HYDROGEL_PACK",
    "VELVETFRUIT_EXTRACT",
    "VEV_4000", "VEV_4500", "VEV_5000", "VEV_5100", "VEV_5200",
    "VEV_5300", "VEV_5400", "VEV_5500", "VEV_6000", "VEV_6500",
]

POSITION_LIMITS: dict[str, int] = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    "VEV_4000": 300, "VEV_4500": 300, "VEV_5000": 300, "VEV_5100": 300,
    "VEV_5200": 300, "VEV_5300": 300, "VEV_5400": 300, "VEV_5500": 300,
    "VEV_6000": 300, "VEV_6500": 300,
}

# Generic mean-reversion thresholds (MarketMaker and its subclasses)
ENTRY_Z = 1.5
EXIT_Z = 0.25

# HP-specific (slow OU + passive MM)
HP_EQUILIBRIUM = round(9990.571806076006, 2)
HP_SIGMA = round(30.78900918189155, 2)
HP_ENTRY_Z = 1.25
HP_EXIT_Z = 0.0
HP_MM_SIZE = 10
HP_MM_INSIDE = 0
HP_MAX_MM_Z = 2.0

# VELVE drives both VELVE-direct and all option positions
VELVE_EQUILIBRIUM = 5250.71
VELVE_SIGMA = 15.63


@dataclass
class TraderData:
    data: int = 0


# ---------------- Base ---------------- #

class MarketTrader:
    """Per-product per-tick context: state snapshot, book, position-aware
    order placement. Subclasses define `compute_z` and `produce_orders`."""

    def __init__(self, product: str, state: TradingState):
        self.product = product
        self.state = state
        self.trader_data = self._load_trader_data()
        self.position_limit = POSITION_LIMITS.get(product.upper(), 0)
        self.current_position = state.position.get(product.upper(), 0)
        self.buy_orders, self.sell_orders = self._load_book()
        self.has_book = bool(self.buy_orders) and bool(self.sell_orders)
        self.buy_committed = 0
        self.sell_committed = 0
        if not self.has_book:
            return
        self.best_bid_price, self.best_bid_volume = next(iter(self.buy_orders.items()))
        self.best_ask_price, self.best_ask_volume = next(iter(self.sell_orders.items()))
        self.wall_mid = self._wallmid()
        self.zscore = self.compute_z()

    def _load_trader_data(self) -> TraderData:
        if not self.state.traderData:
            return TraderData()
        d = json.loads(self.state.traderData).get(self.product)
        return TraderData(data=d["data"]) if d else TraderData()

    def _load_book(self) -> tuple[dict[int, int], dict[int, int]]:
        depth = self.state.order_depths.get(self.product)
        return (depth.buy_orders, depth.sell_orders) if depth else ({}, {})

    def _wallmid(self) -> float:
        return round((min(self.buy_orders) + max(self.sell_orders)) / 2, 2)

    # --- order placement; bid/ask track committed volume so allowed_*() stays accurate --- #

    def bid(self, price: int, volume: int, orders: list[Order]) -> None:
        v = int(abs(volume))
        if v == 0:
            return
        orders.append(Order(self.product, price, v))
        self.buy_committed += v

    def ask(self, price: int, volume: int, orders: list[Order]) -> None:
        v = int(abs(volume))
        if v == 0:
            return
        orders.append(Order(self.product, price, -v))
        self.sell_committed += v

    def allowed_long(self) -> int:
        return self.position_limit - self.current_position - self.buy_committed

    def allowed_short(self) -> int:
        return self.position_limit + self.current_position - self.sell_committed

    def take_asks(self, qty: int, orders: list[Order]) -> None:
        """Buy from sell-side liquidity up to qty."""
        for sp, sv in self.sell_orders.items():
            if qty <= 0:
                return
            v = min(abs(sv), qty)
            self.bid(sp, v, orders)
            qty -= v

    def take_bids(self, qty: int, orders: list[Order]) -> None:
        """Sell into buy-side liquidity up to qty."""
        for bp, bv in self.buy_orders.items():
            if qty <= 0:
                return
            v = min(bv, qty)
            self.ask(bp, v, orders)
            qty -= v

    def compute_z(self) -> float:
        return 0.0


# ---------------- Strategies ---------------- #

class NoOpTrader(MarketTrader):

    def produce_orders(self) -> dict[Product, list[Order]]:
        self.product = cast(Product, self.product)
        return {self.product: []}


class MarketMaker(MarketTrader):
    
    def produce_orders(self) -> dict[Product, list[Order]]:
        orders: list[Order] = []
        self.product = cast(Product, self.product)
        if not self.has_book:
            return {self.product: orders}

        z, pos = self.zscore, self.current_position

        if z > ENTRY_Z and pos <= 0:
            self.take_bids(self.allowed_short(), orders)
        elif z < -ENTRY_Z and pos >= 0:
            self.take_asks(self.allowed_long(), orders)
        elif abs(z) < EXIT_Z and pos != 0:
            if pos > 0:
                self.take_bids(pos, orders)
            else:
                self.take_asks(-pos, orders)

        return {self.product: orders}


class HPTrader(MarketTrader):
    """
    HP-specific trader: slow OU mean-reversion taking + passive MM that joins
    the L1 queue. Captures the ~86% of timesteps where |z|<1.5 that the pure
    take strategy ignores. Does not flatten proactively — rides positions to
    the opposite z extreme to capture the full peak-to-trough swing.
    """

    def compute_z(self) -> float:
        return (self.wall_mid - HP_EQUILIBRIUM) / HP_SIGMA

    def produce_orders(self) -> dict[Product, list[Order]]:
        orders: list[Order] = []
        self.product = cast(Product, self.product)
        if not self.has_book:
            return {self.product: orders}

        z = self.zscore
        pos = self.current_position

        if z > HP_ENTRY_Z:
            for bp, bv in self.buy_orders.items():
                cap = self.allowed_short()
                if cap <= 0:
                    break
                self.ask(bp, min(bv, cap), orders)
        elif z < -HP_ENTRY_Z:
            for sp, sv in self.sell_orders.items():
                cap = self.allowed_long()
                if cap <= 0:
                    break
                self.bid(sp, min(abs(sv), cap), orders)
        elif abs(z) < HP_EXIT_Z and pos != 0:
            if pos > 0:
                remaining = pos
                for bp, bv in self.buy_orders.items():
                    vol = min(bv, remaining)
                    if vol <= 0:
                        break
                    self.ask(bp, vol, orders)
                    remaining -= vol
                    if remaining <= 0:
                        break
            else:
                remaining = -pos
                for sp, sv in self.sell_orders.items():
                    vol = min(abs(sv), remaining)
                    if vol <= 0:
                        break
                    self.bid(sp, vol, orders)
                    remaining -= vol
                    if remaining <= 0:
                        break

        if abs(z) <= HP_MAX_MM_Z:
            mm_bid_price = self.best_bid_price + HP_MM_INSIDE
            mm_ask_price = self.best_ask_price - HP_MM_INSIDE
            if mm_bid_price < mm_ask_price:
                long_room = self.allowed_long()
                short_room = self.allowed_short()
                if long_room > 0:
                    self.bid(mm_bid_price, min(HP_MM_SIZE, long_room), orders)
                if short_room > 0:
                    self.ask(mm_ask_price, min(HP_MM_SIZE, short_room), orders)

        return {self.product: orders}


class VelveTrader(MarketMaker):
    """Mean-reversion on VELVE itself."""

    def compute_z(self) -> float:
        return (self.wall_mid - VELVE_EQUILIBRIUM) / VELVE_SIGMA


class OptionsRevTrader(MarketMaker):
    """Trades VELVE's z-score through option strikes for leveraged exposure."""

    def compute_z(self) -> float:
        depth = self.state.order_depths.get("VELVETFRUIT_EXTRACT")
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return 0.0
        velve_wallmid = round((min(depth.buy_orders) + max(depth.sell_orders)) / 2, 2)
        return (velve_wallmid - VELVE_EQUILIBRIUM) / VELVE_SIGMA


# ---------------- Wiring ---------------- #

TRADERS: dict[str, type[MarketTrader]] = {
    "HYDROGEL_PACK": HPTrader,
    "VELVETFRUIT_EXTRACT": VelveTrader,
    "VEV_4000": NoOpTrader,
    "VEV_4500": OptionsRevTrader,
    "VEV_5000": OptionsRevTrader,
    "VEV_5100": OptionsRevTrader,
    "VEV_5200": OptionsRevTrader,
    "VEV_5300": OptionsRevTrader,
    "VEV_5400": OptionsRevTrader,
    "VEV_5500": OptionsRevTrader,
    "VEV_6000": NoOpTrader,
    "VEV_6500": NoOpTrader,
}


class Trader:
    def run(self, state: TradingState):
        result: dict = {}
        logs: list = []
        outgoing: dict[str, TraderData] = {}

        for product, TraderClass in TRADERS.items():
            trader = TraderClass(product, state)
            outgoing[product] = trader.trader_data
            orders = trader.produce_orders() #pyrefly: ignore
            logs.append([[o.symbol, o.price, o.quantity] for o in orders[product]])
            result.update(orders)

        traderData = json.dumps({p: {"data": td.data} for p, td in outgoing.items()})
        print(f"[DATA] {json.dumps({str(state.timestamp): logs})}")
        return result, 0, traderData

import json
from dataclasses import dataclass
from typing import Literal, cast
from datamodel import Order, TradingState

Product = Literal[
    "GALAXY_SOUNDS_DARK_MATTER",
    "GALAXY_SOUNDS_BLACK_HOLES",
    "GALAXY_SOUNDS_PLANETARY_RINGS",
    "GALAXY_SOUNDS_SOLAR_WINDS",
    "GALAXY_SOUNDS_SOLAR_FLAMES",
    "SLEEP_POD_SUEDE",
    "SLEEP_POD_LAMB_WOOL",
    "SLEEP_POD_POLYESTER",
    "SLEEP_POD_NYLON",
    "SLEEP_POD_COTTON",
    "MICROCHIP_CIRCLE",
    "MICROCHIP_OVAL",
    "MICROCHIP_SQUARE",
    "MICROCHIP_RECTANGLE",
    "MICROCHIP_TRIANGLE",
    "PEBBLES_XS",
    "PEBBLES_S",
    "PEBBLES_M",
    "PEBBLES_L",
    "PEBBLES_XL",
    "ROBOT_VACUUMING",
    "ROBOT_MOPPING",
    "ROBOT_DISHES",
    "ROBOT_LAUNDRY",
    "ROBOT_IRONING",
    "UV_VISOR_YELLOW",
    "UV_VISOR_AMBER",
    "UV_VISOR_ORANGE",
    "UV_VISOR_RED",
    "UV_VISOR_MAGENTA",
    "TRANSLATOR_SPACE_GRAY",
    "TRANSLATOR_ASTRO_BLACK",
    "TRANSLATOR_ECLIPSE_CHARCOAL",
    "TRANSLATOR_GRAPHITE_MIST",
    "TRANSLATOR_VOID_BLUE",
    "PANEL_1X2",
    "PANEL_2X2",
    "PANEL_1X4",
    "PANEL_2X4",
    "PANEL_4X4",
    "OXYGEN_SHAKE_MORNING_BREATH",
    "OXYGEN_SHAKE_EVENING_BREATH",
    "OXYGEN_SHAKE_MINT",
    "OXYGEN_SHAKE_CHOCOLATE",
    "OXYGEN_SHAKE_GARLIC",
    "SNACKPACK_CHOCOLATE",
    "SNACKPACK_VANILLA",
    "SNACKPACK_PISTACHIO",
    "SNACKPACK_STRAWBERRY",
    "SNACKPACK_RASPBERRY",
]

POSITION_LIMITS: dict[str, int] = {
    "GALAXY_SOUNDS_DARK_MATTER": 10,
    "GALAXY_SOUNDS_BLACK_HOLES": 10,
    "GALAXY_SOUNDS_PLANETARY_RINGS": 10,
    "GALAXY_SOUNDS_SOLAR_WINDS": 10,
    "GALAXY_SOUNDS_SOLAR_FLAMES": 10,
    "SLEEP_POD_SUEDE": 10,
    "SLEEP_POD_LAMB_WOOL": 10,
    "SLEEP_POD_POLYESTER": 10,
    "SLEEP_POD_NYLON": 10,
    "SLEEP_POD_COTTON": 10,
    "MICROCHIP_CIRCLE": 10,
    "MICROCHIP_OVAL": 10,
    "MICROCHIP_SQUARE": 10,
    "MICROCHIP_RECTANGLE": 10,
    "MICROCHIP_TRIANGLE": 10,
    "PEBBLES_XS": 10,
    "PEBBLES_S": 10,
    "PEBBLES_M": 10,
    "PEBBLES_L": 10,
    "PEBBLES_XL": 10,
    "ROBOT_VACUUMING": 10,
    "ROBOT_MOPPING": 10,
    "ROBOT_DISHES": 10,
    "ROBOT_LAUNDRY": 10,
    "ROBOT_IRONING": 10,
    "UV_VISOR_YELLOW": 10,
    "UV_VISOR_AMBER": 10,
    "UV_VISOR_ORANGE": 10,
    "UV_VISOR_RED": 10,
    "UV_VISOR_MAGENTA": 10,
    "TRANSLATOR_SPACE_GRAY": 10,
    "TRANSLATOR_ASTRO_BLACK": 10,
    "TRANSLATOR_ECLIPSE_CHARCOAL": 10,
    "TRANSLATOR_GRAPHITE_MIST": 10,
    "TRANSLATOR_VOID_BLUE": 10,
    "PANEL_1X2": 10,
    "PANEL_2X2": 10,
    "PANEL_1X4": 10,
    "PANEL_2X4": 10,
    "PANEL_4X4": 10,
    "OXYGEN_SHAKE_MORNING_BREATH": 10,
    "OXYGEN_SHAKE_EVENING_BREATH": 10,
    "OXYGEN_SHAKE_MINT": 10,
    "OXYGEN_SHAKE_CHOCOLATE": 10,
    "OXYGEN_SHAKE_GARLIC": 10,
    "SNACKPACK_CHOCOLATE": 10,
    "SNACKPACK_VANILLA": 10,
    "SNACKPACK_PISTACHIO": 10,
    "SNACKPACK_STRAWBERRY": 10,
    "SNACKPACK_RASPBERRY": 10,
}


@dataclass
class TraderData:
    data: int = 0

class MarketTrader:

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

    
class MarketMaker(MarketTrader):
    
    def produce_orders(self) -> dict[Product, list[Order]]:
        orders: list[Order] = []
        self.product = cast(Product, self.product)
        if not self.has_book:
            return {self.product: orders}
        
        return {self.product: orders}

class Trader:
    def run(self, state: TradingState):
        result: dict = {}
        logs: list = []
        outgoing: dict[str, TraderData] = {}

        TRADERS: dict[Product, type[MarketMaker]] = {
            "GALAXY_SOUNDS_DARK_MATTER": MarketMaker,
            "GALAXY_SOUNDS_BLACK_HOLES": MarketMaker,
            "GALAXY_SOUNDS_PLANETARY_RINGS": MarketMaker,
            "GALAXY_SOUNDS_SOLAR_WINDS": MarketMaker,
            "GALAXY_SOUNDS_SOLAR_FLAMES": MarketMaker,
            "SLEEP_POD_SUEDE": MarketMaker,
            "SLEEP_POD_LAMB_WOOL": MarketMaker,
            "SLEEP_POD_POLYESTER": MarketMaker,
            "SLEEP_POD_NYLON": MarketMaker,
            "SLEEP_POD_COTTON": MarketMaker,
            "MICROCHIP_CIRCLE": MarketMaker,
            "MICROCHIP_OVAL": MarketMaker,
            "MICROCHIP_SQUARE": MarketMaker,
            "MICROCHIP_RECTANGLE": MarketMaker,
            "MICROCHIP_TRIANGLE": MarketMaker,
            "PEBBLES_XS": MarketMaker,
            "PEBBLES_S": MarketMaker,
            "PEBBLES_M": MarketMaker,
            "PEBBLES_L": MarketMaker,
            "PEBBLES_XL": MarketMaker,
            "ROBOT_VACUUMING": MarketMaker,
            "ROBOT_MOPPING": MarketMaker,
            "ROBOT_DISHES": MarketMaker,
            "ROBOT_LAUNDRY": MarketMaker,
            "ROBOT_IRONING": MarketMaker,
            "UV_VISOR_YELLOW": MarketMaker,
            "UV_VISOR_AMBER": MarketMaker,
            "UV_VISOR_ORANGE": MarketMaker,
            "UV_VISOR_RED": MarketMaker,
            "UV_VISOR_MAGENTA": MarketMaker,
            "TRANSLATOR_SPACE_GRAY": MarketMaker,
            "TRANSLATOR_ASTRO_BLACK": MarketMaker,
            "TRANSLATOR_ECLIPSE_CHARCOAL": MarketMaker,
            "TRANSLATOR_GRAPHITE_MIST": MarketMaker,
            "TRANSLATOR_VOID_BLUE": MarketMaker,
            "PANEL_1X2": MarketMaker,
            "PANEL_2X2": MarketMaker,
            "PANEL_1X4": MarketMaker,
            "PANEL_2X4": MarketMaker,
            "PANEL_4X4": MarketMaker,
            "OXYGEN_SHAKE_MORNING_BREATH": MarketMaker,
            "OXYGEN_SHAKE_EVENING_BREATH": MarketMaker,
            "OXYGEN_SHAKE_MINT": MarketMaker,
            "OXYGEN_SHAKE_CHOCOLATE": MarketMaker,
            "OXYGEN_SHAKE_GARLIC": MarketMaker,
            "SNACKPACK_CHOCOLATE": MarketMaker,
            "SNACKPACK_VANILLA": MarketMaker,
            "SNACKPACK_PISTACHIO": MarketMaker,
            "SNACKPACK_STRAWBERRY": MarketMaker,
            "SNACKPACK_RASPBERRY": MarketMaker,
        }

        for product, TraderClass in TRADERS.items():
            trader = TraderClass(product, state)
            outgoing[product] = trader.trader_data
            orders = trader.produce_orders() 
            logs.append([[o.symbol, o.price, o.quantity] for o in orders[product]]) 
            result.update(orders)

        traderData = json.dumps({p: {"data": td.data} for p, td in outgoing.items()})
        ##print(f"[DATA] {json.dumps({str(state.timestamp): logs})}")
        return result, 0, traderData

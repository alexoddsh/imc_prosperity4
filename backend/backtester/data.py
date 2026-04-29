from collections import defaultdict
from dataclasses import dataclass
from io import StringIO

import numpy as np

from backtester.datamodel import Symbol, Trade
from backtester.file_reader import FileReader

LIMITS = {
    "EMERALDS": 80,
    "TOMATOES": 80,
    "INTARIAN_PEPPER_ROOT": 80,
    "ASH_COATED_OSMIUM": 80,
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
class PriceRow:
    day: int
    timestamp: int
    product: Symbol
    bid_prices: list[int]
    bid_volumes: list[int]
    ask_prices: list[int]
    ask_volumes: list[int]
    mid_price: float
    profit_loss: float


def get_column_values(columns: list[str], indices: list[int]) -> list[int]:
    values = []

    for index in indices:
        value = columns[index]
        if value == "":
            break

        values.append(int(value))

    return values


@dataclass
class ObservationRow:
    timestamp: int
    bidPrice: float
    askPrice: float
    transportFees: float
    exportTariff: float
    importTariff: float
    sugarPrice: float
    sunlightIndex: float


@dataclass
class BacktestData:
    round_num: int
    day_num: int

    prices: dict[int, dict[Symbol, PriceRow]]
    trades: dict[int, dict[Symbol, list[Trade]]]
    observations: dict[int, ObservationRow]
    products: list[Symbol]
    profit_loss: dict[Symbol, float]


def create_backtest_data(
    round_num: int, day_num: int, prices: list[PriceRow], trades: list[Trade], observations: list[ObservationRow]
) -> BacktestData:
    prices_by_timestamp: dict[int, dict[Symbol, PriceRow]] = defaultdict(dict)
    for row in prices:
        prices_by_timestamp[row.timestamp][row.product] = row

    trades_by_timestamp: dict[int, dict[Symbol, list[Trade]]] = defaultdict(lambda: defaultdict(list))
    for trade in trades:
        trades_by_timestamp[trade.timestamp][trade.symbol].append(trade)

    products = sorted(set(row.product for row in prices))
    profit_loss = {product: 0.0 for product in products}

    observations_by_timestamp = {row.timestamp: row for row in observations}

    return BacktestData(
        round_num=round_num,
        day_num=day_num,
        prices=prices_by_timestamp,
        trades=trades_by_timestamp,
        observations=observations_by_timestamp,
        products=products,
        profit_loss=profit_loss,
    )


def has_day_data(file_reader: FileReader, round_num: int, day_num: int) -> bool:
    with file_reader.file([f"round{round_num}", f"prices_round_{round_num}_day_{day_num}.csv"]) as file:
        return file is not None


def read_day_data(file_reader: FileReader, round_num: int, day_num: int, no_names: bool) -> BacktestData:
    _int = int
    _float = float
    _PriceRow = PriceRow

    # --- Prices: fully inlined, zero function calls in hot loop ---
    with file_reader.file([f"round{round_num}", f"prices_round_{round_num}_day_{day_num}.csv"]) as file:
        if file is None:
            raise ValueError(f"Prices data is not available for round {round_num} day {day_num}")

        lines = file.read_text(encoding="utf-8").split("\n")
        end = len(lines) - (1 if not lines[-1] else 0)
        n = end - 1
        prices = [None] * n

        for i in range(1, end):
            c = lines[i].split(";")
            # Inline variable-length extraction — no function calls
            c3, c5, c7 = c[3], c[5], c[7]
            if c3 == "":
                bp = []
            elif c5 == "":
                bp = [_int(c3)]
            elif c7 == "":
                bp = [_int(c3), _int(c5)]
            else:
                bp = [_int(c3), _int(c5), _int(c7)]

            c4, c6, c8 = c[4], c[6], c[8]
            if c4 == "":
                bv = []
            elif c6 == "":
                bv = [_int(c4)]
            elif c8 == "":
                bv = [_int(c4), _int(c6)]
            else:
                bv = [_int(c4), _int(c6), _int(c8)]

            c9, c11, c13 = c[9], c[11], c[13]
            if c9 == "":
                ap = []
            elif c11 == "":
                ap = [_int(c9)]
            elif c13 == "":
                ap = [_int(c9), _int(c11)]
            else:
                ap = [_int(c9), _int(c11), _int(c13)]

            c10, c12, c14 = c[10], c[12], c[14]
            if c10 == "":
                av = []
            elif c12 == "":
                av = [_int(c10)]
            elif c14 == "":
                av = [_int(c10), _int(c12)]
            else:
                av = [_int(c10), _int(c12), _int(c14)]

            prices[i - 1] = _PriceRow(
                _int(c[0]), _int(c[1]), c[2], bp, bv, ap, av, _float(c[15]), _float(c[16])
            )

    # --- Trades: numpy bulk numeric conversion ---
    trades = []
    with file_reader.file([f"round{round_num}", f"trades_round_{round_num}_day_{day_num}.csv"]) as file:
        if file is not None:
            lines = file.read_text(encoding="utf-8").split("\n")
            end = len(lines) - (1 if not lines[-1] else 0)
            tn = end - 1
            if tn > 0:
                raw = [lines[j].split(";") for j in range(1, end)]
                ts_arr = np.array([r[0] for r in raw], dtype=np.int64)
                pr_arr = np.array([r[5] for r in raw], dtype=np.float64).astype(np.int64)
                qt_arr = np.array([r[6] for r in raw], dtype=np.int64)

                trades = [None] * tn
                for i in range(tn):
                    r = raw[i]
                    trades[i] = Trade(
                        symbol=r[3],
                        price=_int(pr_arr[i]),
                        quantity=_int(qt_arr[i]),
                        buyer=r[1],
                        seller=r[2],
                        timestamp=_int(ts_arr[i]),
                    )

    # --- Observations: all numeric, np.loadtxt in C ---
    observations = []
    with file_reader.file([f"round{round_num}", f"observations_round_{round_num}_day_{day_num}.csv"]) as file:
        if file is not None:
            data = np.loadtxt(StringIO(file.read_text(encoding="utf-8")), delimiter=",", skiprows=1)
            if data.ndim == 1:
                data = data.reshape(1, -1)
            on = len(data)
            ts = data[:, 0].astype(np.int64)
            observations = [None] * on
            for i in range(on):
                observations[i] = ObservationRow(
                    timestamp=_int(ts[i]),
                    bidPrice=data[i, 1],
                    askPrice=data[i, 2],
                    transportFees=data[i, 3],
                    exportTariff=data[i, 4],
                    importTariff=data[i, 5],
                    sugarPrice=data[i, 6],
                    sunlightIndex=data[i, 7],
                )

    return create_backtest_data(round_num, day_num, prices, trades, observations)
